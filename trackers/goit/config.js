var config = {
    /* name of the data file; use key `csv` if data file is CSV format, use key `geojson` if data file is geoJSON format */
    geojson: 'https://publicgemdata.nyc3.cdn.digitaloceanspaces.com/interim_maps/goit_map_2026-06.geojson',

    /* Labels for describing the assets */
    assetFullLabel: 'Pipelines',
    assetLabel: 'segments',

    /* configure the table view, selecting which columns to show, how to label them, 
       and designated which column has the link */
    tableHeaders: {
        values: ['name', 'owner', 'parent', 'status', 'all-countries', 'subnational', 'capacity-display', 'units-of-m', 'start-year'],
        labels: ['Name', 'Owner','Parent', 'Status', 'Country/Area(s)', 'Subnational unit (province/state)', 'Capacity', '', 'Start Year'],
        clickColumns: ['name'],
        rightAlign: ['name', 'start-year', 'capacity-display'],
    },

    /* configure the search box; 
       each label has a value with the list of fields to search. Multiple fields might be searched */
    searchFields: {
        'Pipeline name': ['name'],
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

        'owner': {'label': 'Owner'},
        'parent': {'label': 'Parent'},
        'start-year': {'label': 'Start Year'},
    },

    /* ---------------------------- FIELDS TO OVERWRITE FROM site-config.js ---------------------------- */

    color_association: {
        field: 'status',
        values: {
            'operating': 'red',
            'construction': 'blue',
            'proposed': 'blue',
            'mothballed': 'green',
            'cancelled': 'green',
            'retired': 'grey',
            'shelved': 'grey',
            //'': 'black',
        },
    },

    filters: [
        {
            field: 'status',
            values: ['operating', 'proposed', 'construction', 'mothballed', 'cancelled', 'retired', 'shelved',], //''],
            values_labels: ['Operating', 'Proposed', 'Construction', 'Mothballed', 'Cancelled', 'Retired', 'Shelved',], //'Unknown status'],
        },
        {
            field: 'fuel',
            values: ['Oil', 'NGL'],
            filterFunction: (value, selectedValue) => {
                // Check if the value contains the selectedValue (Oil or NGL)
                return value.includes(selectedValue);
            }
        },
    ],

    countryField: 'all-countries',
    includeCapacityByStatusInDetailView: false,

    linkField: 'url', // not project-id because pieces have different ids
    geometries: ['LineString'],
}
