#!/usr/bin/env python3
# coding: utf-8

import pandas as pd
import seaborn as sns
import numpy as np
import cyclopts # This 3rd-party package should be included in the environment.yml file pip section.
from pathlib import Path # This Python Standard Library package should not be added to environment.yml.
import geopandas as gpd
from shapely.geometry import Point


app = cyclopts.App(
    help="Help string for this app.",
    config=cyclopts.config.Json(
        "app_dtd_config.json",  # Use this file, if in cwd (or a parent).
        search_parents=True,
        )
    )


def get_population(config):
    ## Population data 
    state_abbrv = config['us_state'].lower().strip()
    
    pop_dir = f"{config['general_population_path']}{state_abbrv}/"
    person_file = pop_dir+f"/base_population/{state_abbrv}_person.csv"
    hhold_file = pop_dir+f"/base_population/{state_abbrv}_household.csv"
    hloc_file = pop_dir+f"/home_location_assignment/{state_abbrv}_household_residence_assignment.csv"


    
     # Map out all files in /scif directory
    # scif_path = Path('/scif/data/pop/va')
    # if scif_path.exists():
    #     scif_files = [f.name for f in scif_path.iterdir() if f.is_file()]
    #     print(f'Files in /scif: {scif_files}')
    #     # Recursively show structure
    #     for item in scif_path.iterdir():
    #         if item.is_dir():
    #             subfiles = [f.name for f in item.iterdir() if f.is_file()]
    #             print(f'  {item.name}/: {subfiles}')
    # else:
    #     print('/scif/data/pop/va directory does not exist')
    
    print(f'configuration: {config}')

    #### Load person and households data
    print(f'Laoding population file: {person_file}')
    person = pd.read_csv(person_file)
    print(f'Laoding population file: {hhold_file}')
    hhold = pd.read_csv(hhold_file)

    ## Home location data
    print(f'Laoding home location file: {hloc_file}')
    home_loc = pd.read_csv(hloc_file)
    pop = person.merge(home_loc[['hid','blockgroup_id','longitude','latitude']])

    #print(f'Population from {config["us_state"]} is size: {pop.shape[0]}')
    return pop

def augment_population_fields(pop):

    # Mapping synth pop characteristics to similar values as surveillance data columns
    ### County
    pop['county_fips'] = pop["blockgroup_id"].astype(str).str.slice(0,5).astype(int)
    #pop.county.value_counts()

    ### Sex
    #sex_mapping = {1:"Male",2:"Female"}
    sex_mapping = {1:"M",2:"F"}
    pop['patient_current_sex'] = pop['sex'].map(sex_mapping)

    ### Age Groups

    age_group_mapping = {0:'0-9 Years', 1:'10-19 Years',2:'20-29 Years',
                        3:'30-39 Years',4:'40-49 Years',5:'50-59 Years',
                        6:'60-69 Years',7:'70-79 Years',
                        8:'80+  Years',9:'80+  Years',10:'80+  Years'}
    pop['ag'] = pop.age /10
    pop['ag'] = pop.ag.apply(np.floor)
    pop['age_group'] = pop['ag'].map(age_group_mapping)

    ### Race
    full_race_mapping = {1:'White',2:'Black',3: 'American Indian alone',4: 'Alaska Native alone',
                        5:'American Indian and Alaska Native tribes', 6: 'Asian alone',
                        7:'Native Hawaiian and Other Pacific Islander alone',
                        8:'Some Other Race alone', 9: 'Two or More Races'}
    tier_race_mapping = {1:'White',2:'Black',3: 'Native American',4: 'Native American',
                        5:'Native American', 6: 'Asian or Pacific Islander',
                        7:'Asian or Pacific Islander',
                        8:'Other Race', 9: 'Two or more races'}

    pop['tiered_race_ethnicity'] = pop['race'].map(tier_race_mapping)

    ## Override race with Latino  for all Hispanic Ethnicities
    pop.loc[pop.hispanic>1,'tiered_race_ethnicity'] = 'Latino'

    return pop    

def load_polygons_from_geojson(polygon_file):
    print(f"Loading polygons from {polygon_file}")
    polygons_gdf = gpd.read_file(polygon_file)
    print(f"Loaded {len(polygons_gdf)} polygons from GeoJSON")
    print(f"CRS: {polygons_gdf.crs}")
    print(f"Shape: {polygons_gdf.shape}")
    return polygons_gdf



def load_polygons_from_csv(config):
    from shapely.geometry import shape
    import ast
    

    print(f"Loading polygons from {config['csv_path']}")
    df = pd.read_csv(config['csv_path'])
    
    # Parse polygon coordinates and create geometries, skipping NaNs and invalid entries
    def parse_geometry(coord_str):
        try:
            if pd.isna(coord_str):
                return None
            coords = ast.literal_eval(coord_str)
            if not coords or len(coords) == 0 or len(coords[0]) < 3:
                return None
            return shape({'type': 'Polygon', 'coordinates': coords})
        except:
            return None
    
    df['geometry'] = df['polygon.coordinates'].apply(parse_geometry)
    
    # Filter out rows with invalid geometries
    polygons_gdf = gpd.GeoDataFrame(df[df['geometry'].notna()], geometry='geometry', crs="EPSG:4326")
    
    print(f"Loaded {len(polygons_gdf)} valid polygons from CSV (skipped {len(df) - len(polygons_gdf)} invalid entries)")
    print(f"CRS: {polygons_gdf.crs}")
    print(f"Shape: {polygons_gdf.shape}")
    return polygons_gdf


def get_pop_coords(config, pop):
    # Create GeoDataFrame from population data
    # Convert to Point geometries
    geometry = [Point(xy) for xy in zip(pop['longitude'], pop['latitude'])]
    pop_gdf = gpd.GeoDataFrame(pop, geometry=geometry, crs="EPSG:4326")

    print(f"Created GeoDataFrame with {len(pop_gdf)} population records")
    print(f"CRS: {pop_gdf.crs}")

    return pop_gdf

## def load_activity_locations(config):
def find_pop_in_polygons(config, pop_gdf, polygons_gdf):
    # Ensure both GeoDataFrames use the same CRS
    # polygons_gdf = polygons_gdf.to_crs(pop_gdf.crs)

    # Perform spatial join to find which population points fall within which polygons
    pop_in_polygons = gpd.sjoin(pop_gdf, polygons_gdf, how="inner", predicate="within")

    print(f"Found {len(pop_in_polygons)} population records within polygons")
    print("Population example:\n", pop_in_polygons.columns,"\n", pop_in_polygons.head())
    return pop_in_polygons

def count_population_by_category(pop_in_polygons, category_columns):
    # Count population by specified category.
    category_counts = pop_in_polygons.groupby(category_columns)['pid'].count().reset_index()
    category_counts.columns = category_columns + ['subpop_size']

    # Add percentage breakdown: within the first grouping column if present,
    # otherwise as a share of the full table.
    if len(category_columns) > 1:
        parent_col = category_columns[0]
        group_totals = category_counts.groupby(parent_col)['subpop_size'].transform('sum')
        category_counts['subpop_pct'] = (category_counts['subpop_size'] / group_totals * 100).round(1)
    else:
        total = category_counts['subpop_size'].sum()
        category_counts['subpop_pct'] = (category_counts['subpop_size'] / total * 100).round(1)

    return category_counts


def load_socp_description_map(csv_path):
    """Load SOCP code-to-description mapping from a local CSV file."""
    socp_df = pd.read_csv(csv_path, dtype={'occupation_socp': str})
    socp_df['occupation_socp'] = socp_df['occupation_socp'].str.strip()
    socp_df['occupation_socp_description'] = socp_df['occupation_socp_description'].fillna('').str.strip()
    socp_map = dict(zip(socp_df['occupation_socp'], socp_df['occupation_socp_description']))
    print(f"Loaded {len(socp_map)} SOCP descriptions from {csv_path}")
    return socp_map

def export_df_as_html(df, title, filename):
    """Save a styled HTML table to disk without requiring jinja2."""
    # Drop geometry column if present
    df_export = df.copy()
    if 'geometry' in df_export.columns:
        df_export = df_export.drop(columns=['geometry'])
    
    # Build HTML manually
    css = """
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 20px; }
        h1 { color: #333; margin-bottom: 20px; }
        table { border-collapse: collapse; width: 100%; margin: 20px 0; background-color: white; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        th { background-color: #4CAF50; color: white; padding: 12px; text-align: left; font-weight: bold; border-bottom: 2px solid #45a049; }
        td { padding: 10px; border-bottom: 1px solid #ddd; }
        tr:hover { background-color: #f5f5f5; }
        tr:nth-child(even) { background-color: #f9f9f9; }
    </style>
    """
    
    # Build table HTML
    table_html = "<table>\n<thead><tr>"
    for col in df_export.columns:
        table_html += f"<th>{col}</th>"
    table_html += "</tr></thead>\n<tbody>"
    
    for _, row in df_export.iterrows():
        table_html += "<tr>"
        for val in row:
            table_html += f"<td>{val}</td>"
        table_html += "</tr>\n"
    table_html += "</tbody>\n</table>"
    
    full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    {css}
</head>
<body>
    <h1>{title}</h1>
    {table_html}
</body>
</html>"""
    
    with open(filename, "w", encoding='utf-8') as f:
        f.write(full_html)
    print(f"HTML saved to: {filename}")

# Example: Export group_counts without altering notebook displays
# export_df_as_html(group_counts.head(20), "Sub-Population Sizes by Demographic Groups", "subpop_sizes_summary.html")

@app.default
def main(
    # Add config parameters here:
    us_state: str = "va",
    general_population_path: str = "/scif/data/pop/",
    population_path: str = "/project/bii_nssac/production/detailed_populations/ver_2_4_0/va",
    csv_path: str = "/scif/data/site_polygons.csv",
    polygon: str = "DMA",
    socp_description_csv: str = "/scif/data/occupation_socp_descriptions.csv"
    ):
    """
    This is the default function called when the script
    is run from the command line. You can put any lines
    of code you might normally have globally in a
    simple Python "script" here.

    Parameters
    ----------
    us_state: str
        lowercase two-letter state abbreviation to select which US population to access
    general_population_path: str
        The root directory for storing the population digital twins
    csv_path: str
        Path to the CSV file containing polygon information
    
    """

    config = {
        'us_state': us_state,
        'general_population_path': general_population_path,
        'population_path': population_path,
        'csv_path': csv_path,
        'polygon': polygon
    }

    polygon_name_to_file = {
        'DMA': "/scif/data/NationalDMAs.geojson",
        'HSA': "/scif/data/HsaBdry_AK_HI_unmodified.geojson",
        'HRR': "/scif/data/Hrr98Bdry_AK_HI_unmodified.geojson",
        'wastewater': "site_polygons.csv",
        'user_provided': None
        }
    
    polygon_name_to_groupby_col = {
        'DMA': 'NAME',
        'HSA': 'HSANAME',
        'HRR': 'NAME',
        'wastewater': 'site_name',
        'user_provided': None
    }

    print(f'Running with configuration: {config}')
    
    ## Load population
    raw_pop = get_population(config)
    pop = augment_population_fields(raw_pop)

    print(f'Population size from {config["us_state"]}: {pop.shape[0]}')

    ## Load polygons
    polygon_file = polygon_name_to_file.get(config['polygon'], None)
    if "geojson" in polygon_file:
        polygons_gdf = load_polygons_from_geojson(polygon_file)
    elif "csv" in polygon_file:
        polygons_gdf = load_polygons_from_csv(config)
    else:
        print(f"Invalid polygon type specified: {config['polygon']}. Please choose from {list(polygon_name_to_file.keys())}.")
        

    pop_gdf = get_pop_coords(config, pop)
    pop_in_polygons = find_pop_in_polygons(config, pop_gdf, polygons_gdf)
    print(f'Population in polygons is size: {pop_in_polygons.shape[0]}')

    socp_map = load_socp_description_map(socp_description_csv)

#    category_columns = ['place_name', 'race']
    geo_col = polygon_name_to_groupby_col[config['polygon']]

    categories_to_count = ['tiered_race_ethnicity', 'age_group', 'occupation_socp']
    geographic_grouping = config['polygon']
    category_html_template = "/scif/data/population_counts_by_category.html"

    for category_to_count in categories_to_count:
        pop_for_count = pop_in_polygons.copy()
        if category_to_count == 'occupation_socp':
            pop_for_count[category_to_count] = (
                pop_for_count[category_to_count]
                .astype(str)
                .str.strip()
                .map(socp_map)
                .fillna(pop_for_count[category_to_count].astype(str).str.strip())
            )

        category_columns = [geo_col, category_to_count]
        category_counts = count_population_by_category(pop_for_count, category_columns)
        print(f"Population counts by {category_to_count}:\n", category_counts)

        category_html = category_html_template.replace("category", category_to_count)
        print(f"Outputting population counts by {category_to_count} to HTML:", category_html)
        export_df_as_html(
            category_counts,
            f"Population Counts of {category_to_count} by {geographic_grouping}",
            category_html,
        )

    # outpath = Path(outdir)
    # outpath.mkdir(exist_ok=True, parents=True)
    # outpath /= "main_output.txt"
    # output = f"{name}'s age is {age}.\n"
    # print(output)
    # with outpath.open("w") as filehandle:
    #     filehandle.write(output)
    # return output


if __name__ == "__main__":
    app()
