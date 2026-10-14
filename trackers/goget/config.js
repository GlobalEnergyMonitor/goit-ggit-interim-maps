var config = {
    /* GOGET-only map: oil & gas extraction areas, as field-outline polygons plus
       centroid points for the fields with no outline. It reads the same two files
       as the ggit-goget map (no copies), both rebuilt daily from the GEM project
       database by .github/workflows/build-map-data.yml, with the open GOGET bulk
       uploads from Asana overlaid:
       - goget_areas_latest.geojson: field outlines (scripts/build_goget_areas.py);
       - goget_map_latest.geojson: centroids of the fields without an outline, plus
         the new assets that have no GEM id yet (scripts/build_goget_map_data.py). */
    geojson: [
        'https://raw.githubusercontent.com/GlobalEnergyMonitor/goit-ggit-interim-maps/main/trackers/ggit-goget/goget_areas_latest.geojson',
        'https://raw.githubusercontent.com/GlobalEnergyMonitor/goit-ggit-interim-maps/main/trackers/ggit-goget/goget_map_latest.geojson',
    ],

    assetFullLabel: 'extraction areas',
    assetLabel: 'extraction areas',

    downloadNoun: 'data',
    downloadAllNoun: 'all data',

    /* configure the table view, selecting which columns to show, how to label them,
       and designated which column has the link */
    tableHeaders: {
        values: ['PipelineName', 'Owner', 'Parent', 'Operator', 'Status', 'CountriesOrAreas', 'StartState/Province', 'Capacity', 'CapacityUnits', 'StartYear1'],
        labels: ['Name', 'Owner', 'Parent', 'Operator', 'Status', 'Country/Area(s)', 'Subnational unit (province/state)', 'Production', '', 'Start Year'],
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

    /* define fields and how they are displayed (see ggit-goget/config.js for the options) */
    detailView: {
        'PipelineName': {'display': 'heading'},
        'StartLocation': {'display': 'location'},

        'Owner': {'label': 'Owner'},
        'Parent': {'label': 'Parent'},
        'Operator': {'label': 'Operator'},
        'ProjectID': {'label': 'ProjectID'},
        'FuelType': {'label': 'Fuel'},
        'Basin': {'label': 'Basin'},
        'DiscoveryYear': {'label': 'Discovery Year'},
        'FIDYear': {'label': 'FID Year'},
        'StartYear1': {'label': 'Start Year'},
        'ProdOil': {'label': 'Production - Oil', 'trailing-label': 'million bbl/y'},
        'ProdOilYear': {'label': 'Production Year - Oil'},
        'ProdGas': {'label': 'Production - Gas', 'trailing-label': 'million m³/y'},
        'ProdGasYear': {'label': 'Production Year - Gas'},
        'LocationAccuracy': {'label': 'Location Accuracy'},
    },

    /* ---------------------------- FIELDS TO OVERWRITE FROM site-config.js ---------------------------- */

    /* field mappings for the handoff-schema geojson */
    nameField: 'PipelineName',
    projectIdField: 'ProjectID',
    urlField: 'Wiki',
    statusField: 'Status',
    statusDisplayField: 'Status',
    capacityField: 'CapacityBOEd',
    capacityScaledField: 'CapacityBOEd',
    capacityDisplayField: 'Capacity',
    capacityLabelField: 'CapacityUnits',

    /* GOGET status colors, as in the ggit-goget map: dark grey operating, then red /
       orange / yellow for in-development, discovered + exploration, decommissioning */
    color_association: {
        field: 'Status',
        values: {
            'operating': 'dark grey',
            'in-development': 'red',
            'discovered': 'orange',
            'exploration': 'orange',
            'decommissioning': 'yellow',
            'mothballed': 'grey',
            'abandoned': 'grey',
            'cancelled': 'grey',
            'underground gas storage': 'grey',
            'underground carbon storage': 'grey',
            'not found': 'grey',
        },
    },

    filters: [
        {
            field: 'Status',
            values: ['operating', 'in-development', 'discovered', 'exploration', 'decommissioning', 'mothballed', 'abandoned', 'cancelled', 'underground gas storage', 'underground carbon storage', 'not found'],
            values_labels: ['Operating', 'In development', 'Discovered', 'Exploration', 'Decommissioning', 'Mothballed', 'Abandoned', 'Cancelled', 'Underground gas storage', 'Underground carbon storage', 'Not found'],
        },
    ],

    countryField: 'CountriesOrAreas',
    includeCapacityByStatusInDetailView: false,

    linkField: 'Wiki',
    geometries: ['Polygon', 'Point'],

    /* each extraction area appears once, as an outline or else a centroid point,
       so outlines count as their own assets (see ggit-goget/config.js) */
    polygonsAreIndependent: true,

    /* fills only: at world zoom the outlines swamp the fills */
    showPolygonOutlines: false,
}
