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

## Algorithm Summary (Greedy + Multi-Item)
1. Sort items by demand_frequency descending.
2. Remove packing station rows and compute Euclidean distance for each location to (0,0).
3. Sort locations by distance ascending.
4. Multi-item capacity: locations now accept multiple items until either remaining size or remaining weight is exhausted. Residual capacities are tracked.
5. For each item, assign to the first location with sufficient remaining_size and remaining_weight.
6. Output / append to `placement_recommendations.csv` with columns:
	- item_id
	- recommended_location
	- allocated_volume
	- allocated_weight
	- remaining_size (post-placement)
	- remaining_weight (post-placement)
	Items that cannot be placed are tagged `UNPLACED` (allocated_* = 0; remaining_* = blank).

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

## Output (Multi-Item Schema)
placement_recommendations.csv (example rows):
```
item_id,recommended_location,allocated_volume,allocated_weight,remaining_size,remaining_weight
SKU1,A1,0.024,12.0,2.976,188.0
SKU2,A1,0.010,5.0,2.966,183.0
```

## Extending
- (Done) Support multiple items per shelf with residual capacities.
- Add aisle/path metrics instead of straight-line distance.
- Introduce SKU class-based zoning.
- Add Q-table decay & utilization-based expansion triggers.

## Metrics & KPIs
A metrics script `metrics_report.py` computes and appends KPIs to `metrics_history.csv`:

KPIs captured:
- avg_distance: mean distance of placed items.
- weighted_distance: demand-weighted distance (if `inventory_data.csv` has demand_frequency).
- unplaced_rate: fraction of rows with UNPLACED.
- avg_cube_utilization: mean volume utilization of shelves that have any allocated items.
- fragmentation_rate: proportion of utilized shelves with utilization between 0 and 10%.
- total_allocated_volume & capacity_ratio: absolute and relative used cube.
- free_effective_capacity_ratio: remaining_size sum / total capacity (based on latest residual data rows).
- placements_with_capacity_cols_ratio: coverage of new multi-item schema.

Run:
```bash
python metrics_report.py
```
Specify layout explicitly:
```bash
python metrics_report.py --layout locations_data_extended.csv
```
Print-only (no append):
```bash
python metrics_report.py --print-only
```

## Incremental RL Placement Module
Alongside the greedy batch script, the repository provides an incremental placement engine (`incremental_placement.py`) that blends heuristic filtering with a lightweight contextual multi-armed bandit (Q-learning style) to improve shelf selection over time.

### Key Features
- Enriched State: Q-table keys incorporate demand bucket, space bucket (remaining capacity ratio), diversity bucket (distinct items already on a shelf), and shelf ID.
	- Demand bucket width: 25 units.
	- Space buckets: residual ratio bands (0–0.2, 0.2–0.4, 0.4–0.6, 0.6–0.8, 0.8+).
	- Diversity buckets: counts of historical distinct items (0,1,2,3–4,5–7,8+ grouped to 0–4 indices internally).
- Reward Shaping: Combines
	- Distance component: prefer closer shelves.
	- Demand component: mild bonus for higher demand.
	- Fit component: encourages post-placement residual capacity in the 25%–60% band to reduce both fragmentation (tiny leftovers) and underutilization (oversized gaps).
- Epsilon Decay: Exploration rate decays multiplicatively from 0.25 toward a floor of 0.05 across update steps, persisted in `rl_meta.json`.
- Multi-Item Capacity: Respects per-shelf residual volume and weight exactly like the greedy script.
- Backward Compatibility: Legacy Q-keys (demand_bucket, shelf_id) still read; new updates stored using enriched 4-tuple keys.

### Persistence Artifacts
| File | Purpose |
|------|---------|
| `placement_q_table.pkl` | Serialized Q-values (dict). |
| `rl_meta.json` | Stores cumulative steps and current epsilon. |
| `placement_recommendations.csv` | Historical placements + residuals. |

### Typical Usage
Single interactive placement (prompts):
```bash
python incremental_placement.py --interactive
```

Demo item:
```bash
python incremental_placement.py --demo
```

Batch new orders (CSV must contain: item_id,demand_frequency,dimensions,current_stock,weight_per_unit):
```bash
python incremental_placement.py --batch new_orders_sample.csv --episodes 30
```

Override layout (e.g. extended aisles):
```bash
python incremental_placement.py --batch new_orders_sample.csv --layout locations_data_extended.csv
```

### Interpreting Output
Each placement logs the chosen location and current epsilon/steps, e.g.:
```
New item BATCH3 placed at location A3-S14 (epsilon=0.1514, steps=100)
```
Lower epsilon indicates the agent is exploiting learned preferences more often.

### Tuning Knobs
- Episodes per call: `--episodes` (default 40). Higher = more local learning per item (slower).
- Decay pace: adjust `EPSILON_DECAY` in code (default 0.995) for faster/slower convergence.
- Fit band: modify the 0.25–0.60 residual target in `_reward` if utilization goals shift.
- Demand influence: tweak `DEMAND_WEIGHT`.

### Future Ideas
- Diversity penalty/bonus refinement (e.g., discourage excessive item mixing beyond a threshold).
- Time-based Q value decay (forgetting factor) for shifting demand profiles.
- Aisle congestion modeling replacing pure Euclidean distance.
- Periodic rebalancing routine to re-allocate poorly placed items.

---

## License
Internal use example (no explicit license provided).
