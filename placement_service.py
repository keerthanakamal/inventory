from flask import Flask, request, jsonify
from incremental_placement import place_new_item

app = Flask(__name__)

@app.route("/place-item", methods=["POST"])
def place_item():
    data = request.get_json()
    print("DEBUG - microservice received:", data)

    item = parse_new_item(data)
    if "error" in item:
        return jsonify(item), 400
    
    # Call your existing place_new_item function
    try:
        message = place_new_item(item)
        # Extract location from message
        location = None
        if "placed at location" in message:
            location = message.split("placed at location")[-1].strip()
        return jsonify({
            "message": message,
            "recommended_location": location
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
def parse_new_item(data: dict) -> dict:
    """Ensure all required fields exist and are correctly typed."""
    try:
        item_id = str(data["item_id"])
        demand_frequency = int(data.get("demand_frequency") or 0)
        current_stock = int(data.get("current_stock") or 0)
        weight_per_unit = float(data.get("weight_per_unit") or 1.0)
        dimensions = str(data.get("dimensions") or "1x1x1")
        return {
            "item_id": item_id,
            "demand_frequency": demand_frequency,
            "current_stock": current_stock,
            "weight_per_unit": weight_per_unit,
            "dimensions": dimensions
        }
    except KeyError as e:
        return {"error": f"Missing required key: {e}"}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6000, debug=True)
