var config = {
    /* name of the data file; use key `csv` if data file is CSV format, use key `geojson` if data file is geoJSON format.
       Built and published automatically by goit-ggit-data-ops (.github/workflows/build-map-data.yml)
       whenever goit-ggit-pipeline-routes' normalized branch updates: handoff schema
       (same columns as the data-team release, plus map-only columns like RouteCreator),
       null-geometry rows dropped.
       Gas pipelines only — LNG terminals are not in this file (separate map, TBD). */
    geojson: 'https://raw.githubusercontent.com/GlobalEnergyMonitor/goit-ggit-data-ops/map-data/ggit_map_latest.geojson',

    /* Labels for describing the assets */
    assetFullLabel: 'Gas Pipelines',
    assetLabel: 'segments',

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
        'Pipeline name': ['PipelineName'],
        'Project ID': ['ProjectID'],
        'Companies': ['Owner', 'Parent'],
        'Start Year': ['StartYear1'],
    },

    /* define fields and how they are displayed.
      `'display': 'heading'` displays the field in large type
      `'display': 'range'` will show the minimum and maximum values.
      `'display': 'join'` will join together values with a comma separator
      `'display': 'location'` will show the fields over the detail image
      `'label': '...'` prepends a label. If a range, two values for singular and plural.
    */
    detailView: {
        'PipelineName': {'display': 'heading'},
        'SegmentName': {'display': 'subheading'},  // gray segment names under the pipeline name
        'StartLocation': {'display': 'location'},
        'EndLocation': {'display': 'location'},

        'Owner': {'label': 'Owner'},
        'Parent': {'label': 'Parent'},
        'StartYear1': {'label': 'Start Year'},
        'Diameter': {'always-show': true, 'display': 'join', 'label': ['Diameter', 'Diameters'], 'trailing-field': 'DiameterUnits'},
        'LengthKnownKm': {'always-show': true, 'display': 'join', 'label': ['Known length', 'Known lengths'], 'trailing-label': 'km'},
        'LengthEstimateKm': {'always-show': true, 'display': 'join', 'label': ['Estimated length', 'Estimated lengths'], 'trailing-label': 'km'},
        'ProjectID': {'display': 'join', 'label': ['ProjectID', 'ProjectIDs']},
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

    color_association: {
        field: 'Status',
        values: {
            'operating': 'dark grey',
            'construction': 'red',
            'proposed': 'orange',
            'shelved': 'yellow',
            'mothballed': 'grey',
            'cancelled': 'grey',
            'retired': 'grey',
            'idle': 'grey',
            'mixed status': 'grey',
        },
    },

    /* draw order within the line layer, bottom to top; unlisted (grey) statuses
       render below all of these */
    lineSortOrder: ['operating', 'shelved', 'proposed', 'construction'],

    filters: [
        {
            field: 'Status',
            values: ['operating', 'construction', 'proposed', 'shelved', 'mothballed', 'cancelled', 'retired', 'idle', 'mixed status'],
            values_labels: ['Operating', 'Construction', 'Proposed', 'Shelved', 'Mothballed', 'Cancelled', 'Retired', 'Idle', 'Mixed status'],
        },
    ],

    countryField: 'CountriesOrAreas',
    includeCapacityByStatusInDetailView: false,

    linkField: 'Wiki', // not ProjectID because pieces of one pipeline have different ids
    geometries: ['LineString'],

    /* red note in the hover popup and click modal when a segment's route was AI-created
       (RouteCreator is a map-only column appended by pipeline_exports.py in goit-ggit-data-ops) */
    aiRouteNote: {field: 'RouteCreator', value: 'CB', text: 'NOTE: route added by AI'},
}
