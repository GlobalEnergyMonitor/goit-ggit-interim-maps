var config = {
    /* name of the data file; use key `csv` if data file is CSV format, use key `geojson` if data file is geoJSON format */
    geojson: 'https://publicgemdata.nyc3.cdn.digitaloceanspaces.com/interim_maps/ggit-lng_map_2025-11.geojson',

    /* Labels for describing the assets */
    assetFullLabel: 'Gas Infrastructure projects',
    assetLabel: 'projects',

    /* configure the table view, selecting which columns to show, how to label them,
       and designated which column has the link */
    tableHeaders: {
        values: ['name', 'unit-name', 'owner', 'parent', 'capacity-table', 'units-of-m', 'status', 'region', 'all-countries', 'subnational', 'start-year', 'tracker-display'],
        labels: ['Project', 'Unit', 'Owner', 'Parent', 'Capacity', '', 'Status', 'Region', 'Country/Area(s)', 'Subnational unit (province/state)', 'Start year', 'Type'],
        clickColumns: ['name'],
        rightAlign: ['unit-name', 'capacity-table', 'start-year'],
    },

    /* configure the search box;
       each label has a value with the list of fields to search. Multiple fields might be searched */
    searchFields: {
        'Infrastructure Type': ['tracker-display'],
        'Project': ['name'],
        'Companies': ['owner', 'parent'],
        'Start Year': ['start-year'],
    },

    /* define fields and how they are displayed.
      `'display': 'heading'` displays the field in large type
      `'display': 'range'` will show the minimum and maximum values.
      `'display': 'join'` will join together values with a comma separator
      `'display': 'location'` will show the fields over the detail image
      `'label': '...'` prepends a label. If a range, two values for singular and plural.
    */
    detailView: {
        'name': {'display': 'heading'},
        'location-display': {'display': 'location'},

        'unit-name': {'label': 'Unit/Segment'},
        'owner': {'label': 'Owner'},
        'parent': {'label': 'Parent'},
        'start-year': {'label': 'Start Year'},
        'tracker-display': {'label': 'Type'},
    },
    
    /* ---------------------------- FIELDS TO OVERWRITE FROM site-config.js ---------------------------- */

    color_association: {
        field: 'status',
        values: {
            'operating': 'red',
            'proposed': 'green',
            'construction': 'blue',
            'shelved': 'grey',
            'cancelled': 'grey',
            'idled': 'grey',
            'mothballed': 'grey',
            'retired': 'grey',
        },
    },

    filters: [
        {
            field: 'status',
            label: 'Status',
            values: ['operating', 'proposed', 'construction', 'shelved', 'cancelled', 'idled', 'mothballed', 'retired'],
        },
        {
            field: 'tracker-display',
            label: 'Infrastructure Type',
            values: ['LNG import terminal', 'LNG export terminal', 'Gas pipelines'],
            values_labels: ['LNG Terminals (Import)', 'LNG Terminals (Export)', 'Gas Pipelines']
        }
    ],

    countryField: 'all-countries',

    minLineWidth: 1,
    maxLineWidth: 4,
    highZoomMinLineWidth: 2,
    highZoomMaxLineWidth: 5,

    minRadius: 3,
    highZoomMinRadius: 5,
    highZoomMaxRadius: 30,

    geometries: ['Point', 'LineString'],
}