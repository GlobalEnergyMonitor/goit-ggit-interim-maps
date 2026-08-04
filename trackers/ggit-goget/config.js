var config = {
    /* Combined map: GGIT gas pipelines (lines) + GOGET oil & gas extraction areas (points).
       Both sources use the handoff-schema property names, so one config drives both:
       - the GGIT file is the same auto-built one the ggit map uses (rebuilt by
         goit-ggit-data-ops whenever pipeline routes or the sheet change);
       - the GOGET file is a snapshot of the data team's GOGET map export with
         properties renamed to the handoff schema — rebuild it with
         scripts/build_goget_map_data.py and push to refresh. */
    geojson: [
        'https://raw.githubusercontent.com/GlobalEnergyMonitor/goit-ggit-data-ops/map-data/ggit_map_latest.geojson',
        'https://raw.githubusercontent.com/GlobalEnergyMonitor/goit-ggit-interim-maps/main/trackers/ggit-goget/goget_map_latest.geojson',
    ],

    /* Labels for describing the assets */
    assetFullLabel: 'Pipelines + Extraction Areas',
    assetLabel: 'assets',

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

    /* union of the GGIT and GOGET status vocabularies; the color language matches
       the two single-tracker maps (dark grey operating, red construction, orange
       proposed, yellow shelved, grey everything else) */
    color_association: {
        field: 'Status',
        values: {
            'operating': 'dark grey',
            'construction': 'red',
            'proposed': 'orange',
            'shelved': 'yellow',
            'in-development': 'grey',
            'discovered': 'grey',
            'exploration': 'grey',
            'mothballed': 'grey',
            'cancelled': 'grey',
            'decommissioning': 'grey',
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

    filters: [
        {
            field: 'Status',
            values: ['operating', 'construction', 'proposed', 'shelved', 'mothballed', 'cancelled', 'retired', 'idle', 'in-development', 'discovered', 'exploration', 'decommissioning', 'mixed status', 'abandoned', 'underground gas storage', 'not found'],
            values_labels: ['Operating', 'Construction', 'Proposed', 'Shelved', 'Mothballed', 'Cancelled', 'Retired', 'Idle', 'In development', 'Discovered', 'Exploration', 'Decommissioning', 'Mixed status', 'Abandoned', 'Underground gas storage', 'Not found'],
        },
    ],

    countryField: 'CountriesOrAreas',
    includeCapacityByStatusInDetailView: false,

    linkField: 'Wiki', // not ProjectID because pieces of one pipeline have different ids
    geometries: ['LineString', 'Point'],

    /* red note in the hover popup and click modal when a segment's route was AI-created
       (RouteCreator is a map-only column appended by pipeline_exports.py in goit-ggit-data-ops) */
    aiRouteNote: {field: 'RouteCreator', value: 'CB', text: 'NOTE: route added by AI'},
}
