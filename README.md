# Inventory Placement Optimization

Greedy heuristic to assign high-demand items to most accessible warehouse locations.

## Input Files
Place these CSV files in the same directory as `inventory_placement.py` (or provide paths via CLI args):

### item_attributes.csv
Required columns:
- item_id
- demand_frequency
- dimensions (e.g. `10x20x30` -> height x width x depth)
- current_stock

Optional:
- weight_per_unit (defaults to 1.0 if missing)

### warehouse_layout.csv
Required columns:
- location_id
- x_coord
- y_coord
- max_size (volume capacity)
- max_weight (weight capacity)

Optional:
- location_type (rows containing 'packing' are excluded)
- is_packing_station (1/true/yes to exclude)

Packing station assumed at origin (0,0). Any row at (0,0) is treated as packing and removed.

## Algorithm Summary
1. Sort items by demand_frequency descending.
2. Remove packing station rows and compute Euclidean distance for each location to (0,0).
3. Sort locations by distance ascending.
4. For each item (in order), assign to the first unoccupied location whose max_size and max_weight both accommodate the item (volume = h*w*d; total weight = current_stock * weight_per_unit).
5. Output `placement_recommendations.csv` with `item_id,recommended_location`. Items that cannot be placed are tagged `UNPLACED`.

## Usage
```bash
python inventory_placement.py
```
Or with custom paths:
```bash
python inventory_placement.py --items path/to/item_attributes.csv --layout path/to/warehouse_layout.csv --output placement_recommendations.csv --verbose
```

## Example Schemas
item_attributes.csv:
```
item_id,demand_frequency,dimensions,current_stock,weight_per_unit
SKU1,120,10x20x30,50,0.8
SKU2,80,5x10x15,10,1.2
```

warehouse_layout.csv:
```
location_id,x_coord,y_coord,max_size,max_weight,location_type
PACKING,0,0,0,0,packing
A1,2,1,8000,200,slot
A2,3,1,5000,150,slot
```

## Output
placement_recommendations.csv:
```
item_id,recommended_location
SKU1,A1
SKU2,A2
```

## Extending
- Support multiple items per shelf by tracking residual capacities.
- Add aisle/path metrics instead of straight-line distance.
- Introduce SKU class-based zoning.

## License
Internal use example (no explicit license provided).
