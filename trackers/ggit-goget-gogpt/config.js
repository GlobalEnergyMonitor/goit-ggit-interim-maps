var config = {
    /* Combined map: GGIT gas pipelines (lines) + GOGET oil & gas extraction areas
       (field-outline polygons, plus centroid points) + GOGPT oil & gas power plants
       (points, one feature per generating unit) + GGIT LNG terminals (points, one feature
       per terminal unit). All five files use the handoff-schema property names, so one
       config drives them together:
       - the GGIT pipelines file is the same auto-built one the ggit map uses (rebuilt by
         goit-ggit-data-ops whenever pipeline routes or the sheet change);
       - the two GOGET files are the ones the ggit-goget map already loads, read from
         that tracker's folder rather than copied here — see trackers/ggit-goget/config.js
         for how they're built and why each field appears exactly once;
       - gogpt_map_latest.geojson is a snapshot of the data team's GOGPT map export with
         properties renamed to the handoff schema — rebuild it with
         scripts/build_gogpt_map_data.py;
       - lng_map_latest.geojson comes straight from the GEM project database (there is no
         published LNG map export to rename) — rebuild it with
         scripts/build_lng_map_data.py. The LNG terminals are deliberately only on this
         map: the ggit map stays gas pipelines only. */
    geojson: [
        'https://raw.githubusercontent.com/GlobalEnergyMonitor/goit-ggit-data-ops/map-data/ggit_map_latest.geojson',
        'https://raw.githubusercontent.com/GlobalEnergyMonitor/goit-ggit-interim-maps/main/trackers/ggit-goget/goget_areas_latest.geojson',
        'https://raw.githubusercontent.com/GlobalEnergyMonitor/goit-ggit-interim-maps/main/trackers/ggit-goget/goget_map_latest.geojson',
        'https://raw.githubusercontent.com/GlobalEnergyMonitor/goit-ggit-interim-maps/main/trackers/ggit-goget-gogpt/gogpt_map_latest.geojson',
        'https://raw.githubusercontent.com/GlobalEnergyMonitor/goit-ggit-interim-maps/main/trackers/ggit-goget-gogpt/lng_map_latest.geojson',
    ],

    /* Labels for describing the assets. assetFullLabel is deliberately short: it sets the
       legend's summary line ('Total assets selected'), which was the widest thing in the
       card and stretched the whole legend. The four legend sections name the trackers. */
    assetFullLabel: 'assets',
    assetLabel: 'assets',

    /* this map isn't only pipeline routes, so the download buttons say 'data' */
    downloadNoun: 'data',

    /* configure the table view, selecting which columns to show, how to label them,
       and designated which column has the link */
    tableHeaders: {
        values: ['PipelineName', 'Owner', 'Parent', 'Status', 'CountriesOrAreas', 'StartState/Province', 'Capacity', 'CapacityUnits', 'StartYear1'],
        labels: ['Name', 'Owner','Parent', 'Status', 'Country/Area(s)', 'Subnational unit (province/state)', 'Capacity', '', 'Start Year'],
        clickColumns: ['PipelineName'],
        rightAlign: ['PipelineName', 'StartYear1', 'Capacity'],
    },

    /* configure the search box;
       each label has a value with the list of fields to search. Multiple fields might be searched */
    searchFields: {
        'Name': ['PipelineName'],
        'Project ID': ['ProjectID', 'UnitID'],
        'Companies': ['Owner', 'Parent', 'Operator'],
        'Start Year': ['StartYear1'],
    },

    /* define fields and how they are displayed.
      `'display': 'heading'` displays the field in large type
      `'display': 'range'` will show the minimum and maximum values.
      `'display': 'join'` will join together values with a comma separator
      `'display': 'location'` will show the fields over the detail image
      `'label': '...'` prepends a label. If a range, two values for singular and plural.
      Fields from all three trackers coexist here: a feature that lacks a field simply
      doesn't display that row. */
    detailView: {
        'PipelineName': {'display': 'heading'},
        'SegmentName': {'display': 'subheading'},  // gray segment/unit names under the project name
        'StartLocation': {'display': 'location'},
        'EndLocation': {'display': 'location'},

        'Owner': {'label': 'Owner'},
        'Parent': {'label': 'Parent'},
        'Operator': {'label': 'Operator'},
        'StartYear1': {'label': 'Start Year'},

        /* the reported capacity of every segment/unit in the card, each with its own unit
           (MMcf/d, million boe/y, MW). The shell's built-in capacity row is off here
           (includeCapacityByStatusInDetailView), and it would otherwise total the
           display-only CapacityMapScale values rather than these. */
        'Capacity': {'display': 'join', 'label': ['Capacity', 'Capacities'], 'trailing-field': 'CapacityUnits'},

        /* pipeline (GGIT) fields */
        'Diameter': {'display': 'join', 'label': ['Diameter', 'Diameters'], 'trailing-field': 'DiameterUnits'},
        'LengthKnownKm': {'display': 'join', 'label': ['Known length', 'Known lengths'], 'trailing-label': 'km'},
        'LengthEstimateKm': {'display': 'join', 'label': ['Estimated length', 'Estimated lengths'], 'trailing-label': 'km'},
        'ProjectID': {'display': 'join', 'label': ['ProjectID', 'ProjectIDs']},
        'RouteAccuracy': {'display': 'join', 'label': ['Route accuracy', 'Route accuracies']},
        'RouteCreator': {'display': 'join', 'label': ['Route creator', 'Route creators']},

        /* extraction-area (GOGET) fields */
        'DiscoveryYear': {'label': 'Discovery Year'},
        'FIDYear': {'label': 'FID Year'},
        'ProdOil': {'label': 'Production - Oil', 'trailing-label': 'million bbl/y'},
        'ProdOilYear': {'label': 'Production Year - Oil'},
        'ProdGas': {'label': 'Production - Gas', 'trailing-label': 'million m³/y'},
        'ProdGasYear': {'label': 'Production Year - Gas'},
        'LocationAccuracy': {'label': 'Location Accuracy'},

        /* power-plant (GOGPT) fields; FuelType is also carried by the GOGET areas and the
           LNG terminals, and UnitID by the terminals */
        'UnitID': {'display': 'join', 'label': ['Unit ID', 'Unit IDs']},
        'FuelType': {'label': 'Fuel'},
        'TechType': {'label': 'Technology'},

        /* LNG terminal fields */
        'FacilityType': {'label': 'Facility type'},
    },

    /* ---------------------------- FIELDS TO OVERWRITE FROM site-config.js ---------------------------- */

    /* field mappings for the handoff-schema geojson */
    nameField: 'PipelineName',
    projectIdField: 'ProjectID',  // shown in the hover popup (segment/unit-level id)
    segmentNameField: 'SegmentName',  // gray segment/unit name in the hover popup
    urlField: 'Wiki',
    statusField: 'Status',
    statusDisplayField: 'Status',
    capacityField: 'CapacityMapScale',
    capacityScaledField: 'CapacityMapScale',
    capacityDisplayField: 'Capacity',
    capacityLabelField: 'CapacityUnits',

    /* union of the GGIT pipeline, GOGET, GOGPT and LNG-terminal status vocabularies. The
       vocabularies only share statuses that mean the same thing in each tracker, so one
       map covers all four: dark grey operating, then red / orange / light red / yellow for
       the pre-operating and post-operating stages of each tracker (pipelines:
       construction, proposed, shelved; extraction areas: in-development, discovered +
       exploration, decommissioning; power plants: construction, pre-construction,
       announced, shelved; LNG terminals: construction, proposed, shelved), grey everything
       else. 'idled' is the LNG tracker's spelling of the pipelines' 'idle'. */
    color_association: {
        field: 'Status',
        values: {
            'operating': 'dark grey',
            'construction': 'red',
            'proposed': 'orange',
            'pre-construction': 'orange',
            'announced': 'light red',
            'shelved': 'yellow',
            'in-development': 'red',
            'discovered': 'orange',
            'exploration': 'orange',
            'decommissioning': 'yellow',
            'mothballed': 'grey',
            'cancelled': 'grey',
            'retired': 'grey',
            'idle': 'grey',
            'idled': 'grey',
            'mixed status': 'grey',
            'abandoned': 'grey',
            'underground gas storage': 'grey',
            'not found': 'grey',
        },
    },

    /* draw order within the line layer, bottom to top; unlisted (grey) statuses
       render below all of these */
    lineSortOrder: ['operating', 'shelved', 'proposed', 'construction'],

    /* One legend section per tracker, and one shared circle-scaling field, both built by
       copying a source's own values into a field only that source carries (see
       makeDerivedFields in site.js). A rule matches on geometry, on the Tracker property,
       or both — geometry alone can't separate the GOGET centroids from the GOGPT plants,
       since both are points.

       Status → PipelineStatus / ExtractionStatus / PlantStatus / TerminalStatus: a single
       field can't carry four legend sections (duplicate ids, one shared checkbox list),
       and site.js skips a section for features that lack its field, so each section
       filters just its own tracker while the map paint keeps reading the shared Status.

       CapacityBOEd → CapacityMapScale: marker size comes from one field, and plant
       capacity is nameplate MW while pipeline and extraction capacity is boe/d. The GOGPT
       file supplies its own CapacityMapScale (MW × 100, a display-only number — see
       build_gogpt_map_data.py) and the LNG file supplies boe/d converted from whatever
       unit each terminal recorded (build_lng_map_data.py); the other two sources just
       reuse their boe/d value. The real figures stay in Capacity/CapacityUnits, which is
       what the detail card, the table and the downloads show. */
    derivedFields: [
        {field: 'PipelineStatus', from: 'Status', geometries: ['LineString', 'MultiLineString']},
        {field: 'ExtractionStatus', from: 'Status', where: {field: 'Tracker', value: 'GOGET'}},
        {field: 'PlantStatus', from: 'Status', where: {field: 'Tracker', value: 'GOGPT'}},
        {field: 'TerminalStatus', from: 'Status', where: {field: 'Tracker', value: 'GGIT-LNG'}},
        {field: 'CapacityMapScale', from: 'CapacityBOEd', geometries: ['LineString', 'MultiLineString']},
        {field: 'CapacityMapScale', from: 'CapacityBOEd', where: {field: 'Tracker', value: 'GOGET'}},
    ],

    /* Three kinds of point on one map, all sharing the status colors, so shape carries the
       tracker: power plants are squares, LNG terminals triangles, and the GOGET extraction
       centroids stay circles. Multi-status groups still get their pie split, just clipped
       to the shape (see MARKER_CLIP_PATHS in site.js). */
    markerShapes: [
        {field: 'Tracker', value: 'GOGPT', shape: 'square'},
        {field: 'Tracker', value: 'GGIT-LNG', shape: 'triangle'},
    ],

    filters: [
        {
            field: 'PipelineStatus',
            label: 'Gas pipelines',
            showColorDots: true,
            values: ['operating', 'construction', 'proposed', 'shelved', 'mothballed', 'cancelled', 'retired', 'idle', 'mixed status'],
            values_labels: ['Operating', 'Construction', 'Proposed', 'Shelved', 'Mothballed', 'Cancelled', 'Retired', 'Idle', 'Mixed status'],
        },
        {
            field: 'ExtractionStatus',
            label: 'Oil &amp; gas extraction areas',
            showColorDots: true,
            values: ['operating', 'in-development', 'discovered', 'exploration', 'decommissioning', 'mothballed', 'abandoned', 'cancelled', 'underground gas storage', 'not found'],
            values_labels: ['Operating', 'In development', 'Discovered', 'Exploration', 'Decommissioning', 'Mothballed', 'Abandoned', 'Cancelled', 'Underground gas storage', 'Not found'],
        },
        {
            field: 'PlantStatus',
            label: 'Oil &amp; gas power plants',
            showColorDots: true,
            dotShape: 'square',  // these draw as squares on the map
            values: ['operating', 'construction', 'pre-construction', 'announced', 'shelved', 'mothballed', 'retired', 'cancelled'],
            values_labels: ['Operating', 'Construction', 'Pre-construction', 'Announced', 'Shelved', 'Mothballed', 'Retired', 'Cancelled'],
        },
        {
            field: 'TerminalStatus',
            label: 'LNG terminals',
            showColorDots: true,
            dotShape: 'triangle',  // these draw as triangles on the map
            values: ['operating', 'construction', 'proposed', 'shelved', 'mothballed', 'idled', 'retired', 'cancelled'],
            values_labels: ['Operating', 'Construction', 'Proposed', 'Shelved', 'Mothballed', 'Idled', 'Retired', 'Cancelled'],
        },
    ],

    countryField: 'CountriesOrAreas',
    includeCapacityByStatusInDetailView: false,

    linkField: 'Wiki', // not ProjectID because pieces of one pipeline have different ids
    geometries: ['Polygon', 'LineString', 'Point'],

    /* Each extraction area appears exactly once — as an outline if the database has
       one for it, otherwise as a centroid point (build_goget_map_data.py drops the
       points that would duplicate an outline) — so outlines count as their own
       assets. Leaving this false would instead drop every outline from the legend
       tally: grouping keys off linkField + coordinates[0],[1], which a polygon's
       ring array never matches, so an outline is always alone in its group. */
    polygonsAreIndependent: true,

    /* fills only: at world zoom a 2px outline on every field swamped the fill it was
       tracing, and the outlines of neighbouring fields ran together */
    showPolygonOutlines: false,

    /* extra rows under the ProjectID line in the hover popup, per segment; the GOGET
       extraction points and the GOGPT units carry neither field, so they simply don't
       get these rows */
    hoverFields: [
        {field: 'RouteAccuracy', label: 'Route accuracy'},
        {field: 'RouteCreator', label: 'Route creator'},
    ],

    /* red note in the hover popup and click modal when a segment's route was AI-created
       (RouteCreator is a map-only column appended by pipeline_exports.py in goit-ggit-data-ops) */
    aiRouteNote: {field: 'RouteCreator', value: 'CB', text: 'NOTE: route added by AI'},
}
