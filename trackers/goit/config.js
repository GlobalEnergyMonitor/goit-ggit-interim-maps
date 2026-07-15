var config = {
    /* name of the data file; use key `csv` if data file is CSV format, use key `geojson` if data file is geoJSON format.
       Built and published automatically by goit-ggit-data-ops (.github/workflows/build-map-data.yml)
       whenever goit-ggit-pipeline-routes' normalized branch updates: handoff schema
       (same columns as the data-team release), null-geometry rows dropped. */
    geojson: 'https://raw.githubusercontent.com/GlobalEnergyMonitor/goit-ggit-data-ops/map-data/goit_map_latest.geojson',

    /* Labels for describing the assets */
    assetFullLabel: 'Pipelines',
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
        'StartLocation': {'display': 'location'},
        'EndLocation': {'display': 'location'},

        'Owner': {'label': 'Owner'},
        'Parent': {'label': 'Parent'},
        'StartYear1': {'label': 'Start Year'},
    },

    /* ---------------------------- FIELDS TO OVERWRITE FROM site-config.js ---------------------------- */

    /* field mappings for the handoff-schema geojson */
    nameField: 'PipelineName',
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
            field: 'Status',
            values: ['operating', 'proposed', 'construction', 'mothballed', 'cancelled', 'retired', 'shelved',], //''],
            values_labels: ['Operating', 'Proposed', 'Construction', 'Mothballed', 'Cancelled', 'Retired', 'Shelved',], //'Unknown status'],
        },
        {
            field: 'Fuel',
            values: ['Oil', 'NGL'],
            filterFunction: (value, selectedValue) => {
                // Check if the value contains the selectedValue (Oil or NGL)
                return value.includes(selectedValue);
            }
        },
    ],

    countryField: 'CountriesOrAreas',
    includeCapacityByStatusInDetailView: false,

    linkField: 'Wiki', // not ProjectID because pieces of one pipeline have different ids
    geometries: ['LineString'],
}
