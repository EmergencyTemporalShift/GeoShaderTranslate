import json
import sys
import argparse

# A set of standard nodes shared natively between Geometry and Shader node groups
SHARED_MATH_NODES = {
    # Core structural/routing nodes
    "NodeGroupInput", "NodeGroupOutput", "NodeReroute", "NodeFrame",

    # Standard scalar & vector math
    "ShaderNodeMath", "ShaderNodeVectorMath", "ShaderNodeValue",
    "ShaderNodeMix", "ShaderNodeClamp", "ShaderNodeMapRange",
    "ShaderNodeValToRGB",

    # Vector component manipulation (shared natively under ShaderNode names)
    "ShaderNodeSeparateXYZ", "ShaderNodeCombineXYZ", "ShaderNodeVectorRotate",

    # Color component manipulation (frequently used for math/vector packing)
    "ShaderNodeSeparateColor", "ShaderNodeCombineColor",

    # Pure mathematical texture generation
    "ShaderNodeTexWhiteNoise"
}

def convert_nodes(input_text, output_file=None):
    # Filter out any comment lines added by the Blender add-on from the raw text
    json_string = "\n".join(line for line in input_text.splitlines() if not line.lstrip().startswith('#'))

    try:
        data = json.loads(json_string)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse JSON. {e}", file=sys.stderr)
        return

    current_type = data.get("type")

    # Determine the target translation type
    if current_type == "GEOMETRY":
        target_type = "SHADER"
        target_group_idname = "ShaderNodeGroup"
    elif current_type == "SHADER":
        target_type = "GEOMETRY"
        target_group_idname = "GeometryNodeGroup"
    else:
        print(f"Error: Unknown group type '{current_type}'.", file=sys.stderr)
        return

    print(f"Converting from {current_type} to {target_type}...", file=sys.stderr)
    data["type"] = target_type

    # Update the outer group wrapper
    if "nodes" in data:
        for node in data["nodes"]:
            node["bl_idname"] = target_group_idname

    warnings = []

    # Iterate through the inner node tree to validate nodes and clean up properties
    for tree_name, tree_data in data.get("node_trees", {}).items():

        # Cleanup read-only properties that crash the import
        if "props" in tree_data:
            tree_data["props"].pop("sv_splash_data", None)

        # Validate internal nodes
        for node in tree_data.get("nodes", []):
            idname = node.get("bl_idname", "")
            node_name = node.get("props", {}).get("name", "Unknown")

            if idname not in SHARED_MATH_NODES:
                if target_type == "SHADER" and ("GeometryNode" in idname or "FunctionNode" in idname):
                    warnings.append(f"  - '{idname}' ('{node_name}') has no direct shader equivalent.")
                elif target_type == "GEOMETRY" and "ShaderNode" in idname:
                    warnings.append(f"  - '{idname}' ('{node_name}') is a shader-specific node and may break in geometry nodes.")
                else:
                    warnings.append(f"  - '{idname}' ('{node_name}') is unrecognized and might not translate cleanly.")

    # Print out any incompatibilities safely to stderr
    if warnings:
        print("\n--- Compatibility Warnings ---", file=sys.stderr)
        for w in warnings:
            print(w, file=sys.stderr)
        print("------------------------------\n", file=sys.stderr)
    else:
        print("All internal nodes look natively compatible!\n", file=sys.stderr)

    # Output the result
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Successfully saved to {output_file}", file=sys.stderr)
    else:
        # Dump directly to stdout, padding with spaces to overwrite Wayland ghost buffers
        json_output = json.dumps(data, indent=2)
        print(json_output + " " * 2048)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert Blender Copy/Paste Node JSONs between Shader and Geometry.")
    parser.add_argument("input", nargs="?", help="Input JSON file path (leave blank to read from clipboard/stdin)")
    parser.add_argument("-o", "--output", help="Output JSON file path (prints to stdout if omitted)")
    args = parser.parse_args()

    # Read from a file if one is provided
    if args.input:
        with open(args.input, 'r') as f:
            raw_input_text = f.read()
    # Otherwise, read directly from the piped input
    else:
        raw_input_text = sys.stdin.read()
        if not raw_input_text.strip():
            print("Error: No input provided. Provide a file or pipe data into the script.", file=sys.stderr)
            sys.exit(1)

    convert_nodes(raw_input_text, args.output)
