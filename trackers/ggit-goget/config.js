var config = {
    /* Combined map: GGIT gas pipelines (lines) + GOGET oil & gas extraction areas
       (field-outline polygons, plus centroid points). All three sources use the
       handoff-schema property names, so one config drives them together:
       - the GGIT file is the same auto-built one the ggit map uses (rebuilt by
         goit-ggit-data-ops whenever pipeline routes or the sheet change);
       - goget_map_latest.geojson is a snapshot of the data team's GOGET map export
         with properties renamed to the handoff schema — rebuild it with
         scripts/build_goget_map_data.py;
       - goget_areas_latest.geojson is the field outlines, read straight from the
         GEM project database (project_geospatial.wkt) by
         scripts/build_goget_areas.py — fresher than the release sheet, and the
         only source where outlines over 32k characters survive intact. */
    geojson: [
        'https://raw.githubusercontent.com/GlobalEnergyMonitor/goit-ggit-data-ops/map-data/ggit_map_latest.geojson',
        'https://raw.githubusercontent.com/GlobalEnergyMonitor/goit-ggit-interim-maps/main/trackers/ggit-goget/goget_areas_latest.geojson',
        'https://raw.githubusercontent.com/GlobalEnergyMonitor/goit-ggit-interim-maps/main/trackers/ggit-goget/goget_map_latest.geojson',
    ],

    /* Labels for describing the assets. assetFullLabel is deliberately short: it sets the
       legend's summary line ('Total assets selected'), which was the widest thing in the
       card and stretched the whole legend. The two legend sections name the trackers. */
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
        'Project ID': ['ProjectID'],
        'Companies': ['Owner', 'Parent', 'Operator'],
        'Start Year': ['StartYear1'],
    },

    /* define fields and how they are displayed.
      `'display': 'heading'` displays the field in large type
      `'display': 'range'` will show the minimum and maximum values.
      `'display': 'join'` will join together values with a comma separator
      `'display': 'location'` will show the fields over the detail image
      `'label': '...'` prepends a label. If a range, two values for singular and plural.
      Pipeline-only and extraction-only fields coexist here: a feature that lacks
      a field simply doesn't display that row. */
    detailView: {
        'PipelineName': {'display': 'heading'},
        'SegmentName': {'display': 'subheading'},  // gray segment names under the pipeline name
        'StartLocation': {'display': 'location'},
        'EndLocation': {'display': 'location'},

        'Owner': {'label': 'Owner'},
        'Parent': {'label': 'Parent'},
        'Operator': {'label': 'Operator'},
        'StartYear1': {'label': 'Start Year'},

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
    },

    /* ---------------------------- FIELDS TO OVERWRITE FROM site-config.js ---------------------------- */

    /* field mappings for the handoff-schema geojson */
    nameField: 'PipelineName',
    projectIdField: 'ProjectID',  // shown in the hover popup (segment-level id)
    segmentNameField: 'SegmentName',  // gray segment name in the hover popup
    urlField: 'Wiki',
    statusField: 'Status',
    statusDisplayField: 'Status',
    capacityField: 'CapacityBOEd',
    capacityScaledField: 'CapacityBOEd',
    capacityDisplayField: 'Capacity',
    capacityLabelField: 'CapacityUnits',

    /* union of the GGIT and GOGET status vocabularies. The two vocabularies only share
       statuses that are grey anyway, so one map covers both: dark grey operating, then
       red / orange / yellow for the pre-operating and post-operating stages of each
       tracker (pipelines: construction, proposed, shelved; extraction areas:
       in-development, discovered + exploration, decommissioning), grey everything else. */
    color_association: {
        field: 'Status',
        values: {
            'operating': 'dark grey',
            'construction': 'red',
            'proposed': 'orange',
            'shelved': 'yellow',
            'in-development': 'red',
            'discovered': 'orange',
            'exploration': 'orange',
            'decommissioning': 'yellow',
            'mothballed': 'grey',
            'cancelled': 'grey',
            'retired': 'grey',
            'idle': 'grey',
            'mixed status': 'grey',
            'abandoned': 'grey',
            'underground gas storage': 'grey',
            'not found': 'grey',
        },
    },

    /* draw order within the line layer, bottom to top; unlisted (grey) statuses
       render below all of these */
    lineSortOrder: ['operating', 'shelved', 'proposed', 'construction'],

    /* One legend section per tracker. Both sections filter on Status, but a single field
       can't carry two legend sections (duplicate ids, one shared checkbox list), so Status
       is copied into a per-geometry field: lines (GGIT pipelines) get PipelineStatus,
       points (GOGET extraction areas) get ExtractionStatus. Features only carry their own
       source's field, and site.js skips a section for features that lack its field, so
       each section filters just its own tracker. */
    derivedFields: [
        {field: 'PipelineStatus', from: 'Status', geometries: ['LineString', 'MultiLineString']},
        {field: 'ExtractionStatus', from: 'Status', geometries: ['Point', 'MultiPoint', 'Polygon', 'MultiPolygon']},
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
       extraction points carry neither field, so they simply don't get these rows */
    hoverFields: [
        {field: 'RouteAccuracy', label: 'Route accuracy'},
        {field: 'RouteCreator', label: 'Route creator'},
    ],

    /* red note in the hover popup and click modal when a segment's route was AI-created
       (RouteCreator is a map-only column appended by pipeline_exports.py in goit-ggit-data-ops) */
    aiRouteNote: {field: 'RouteCreator', value: 'CB', text: 'NOTE: route added by AI'},
}
