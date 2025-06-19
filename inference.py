#!/usr/bin/env python3
"""
Paper Model Inference Script
Converts OBJ files to unfolded SVG paper models using Blender's bpy library.

Usage:
    python inference.py <input_obj_path> <output_svg_path>
    
Example:
    python inference.py models/WeirdShape.obj output/WeirdShape_unfolded.svg

Note: The "Not freed memory blocks" message at the end is just debug output
from Blender's memory debugging system and doesn't indicate a real memory leak.
"""

import bpy
import os
import sys
import argparse
from pathlib import Path
import logging

def setup_blender_environment():
    """Set up Blender environment for paper model export"""
    try:
        # Disable undo system to reduce memory usage
        bpy.context.preferences.edit.undo_steps = 0
        
        # Clear existing scene
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False, confirm=False)
        
        # Enable OBJ import addon if not already enabled
        try:
            bpy.ops.preferences.addon_enable(module="io_scene_obj")
        except:
            pass  # Already enabled or not needed
            
    except Exception as e:
        raise RuntimeError(f"Failed to setup Blender environment: {e}")

def install_paper_model_addon():
    """Install and enable the paper model export addon"""
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    addon_path = os.path.join(repo_dir, "io_export_paper_model.py")
    
    if not os.path.exists(addon_path):
        raise FileNotFoundError(f"Paper model addon not found at: {addon_path}")
    
    # Install the addon
    try:
        bpy.ops.preferences.addon_install(
            filepath=addon_path,
            overwrite=True
        )
        bpy.ops.preferences.addon_enable(module="io_export_paper_model")
        print("✓ Paper model addon installed and enabled")
    except Exception as e:
        raise RuntimeError(f"Failed to install paper model addon: {e}")

def import_obj_file(obj_path):
    """Import OBJ file and return the imported object"""
    if not os.path.exists(obj_path):
        raise FileNotFoundError(f"OBJ file not found: {obj_path}")
    
    print(f"Importing OBJ file: {obj_path}")
    
    # Clear any existing selection first
    try:
        bpy.ops.object.select_all(action='DESELECT')
    except:
        pass
    
    # Import the OBJ file
    bpy.ops.wm.obj_import(
        filepath=obj_path,
        filter_glob="*.obj;*.mtl"
    )
    
    # Get the imported object
    imported = bpy.context.selected_objects
    if not imported:
        raise RuntimeError(f"No objects imported from {obj_path}")
    
    obj = imported[0]
    bpy.context.view_layer.objects.active = obj
    print(f"✓ Imported object: {obj.name}")
    
    return obj

def export_paper_model(output_path):
    """Export the active object as a paper model SVG"""
    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Ensure .svg extension
    if not output_path.lower().endswith('.svg'):
        output_path += '.svg'
    
    print(f"Exporting paper model to: {output_path}")
    
    # Export the paper model
    bpy.ops.export_mesh.paper_model(
        filepath=output_path,
        file_format='SVG'
    )
    
    if os.path.exists(output_path):
        print(f"✓ Paper model exported successfully: {output_path}")
        return output_path
    else:
        raise RuntimeError(f"Export failed - file not created: {output_path}")

def process_single(input_path, output_path, fmt, verbose):
    """Process a single OBJ file to unfolded paper model"""
    try:
        # Set up Blender environment
        setup_blender_environment()
        
        # Install paper model addon
        install_paper_model_addon()
        
        # Import OBJ file
        obj = import_obj_file(input_path)
        
        # Export paper model
        output_file = export_paper_model(output_path)
        
        print(f"✓ Success! Paper model created: {output_file}")
        return output_file
        
    except Exception as e:
        print(f"❌ Error processing {input_path}: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return None

def process_batch(input_dir, output_dir, fmt, verbose):
    """Process all OBJ files in a directory"""
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    obj_files = list(input_dir.glob('*.obj'))
    if not obj_files:
        print(f"No OBJ files found in {input_dir}")
        return
    
    print(f"Found {len(obj_files)} OBJ files to process")
    
    successful = 0
    failed = 0
    
    for obj_file in obj_files:
        base = obj_file.stem
        out_file = output_dir / f"{base}_unfolded.{fmt}"
        print(f"\nProcessing {obj_file.name} -> {out_file.name}")
        
        result = process_single(str(obj_file), str(out_file), fmt, verbose)
        if result:
            successful += 1
        else:
            failed += 1
    
    print(f"\n📊 Batch processing complete!")
    print(f"   Successful: {successful}")
    print(f"   Failed: {failed}")
    print(f"   Total: {len(obj_files)}")
    
    if failed > 0:
        print("\nNote: Any 'Not freed memory blocks' messages are just debug output from Blender's memory debugging system.")

def main():
    parser = argparse.ArgumentParser(
        description="Convert OBJ files to unfolded SVG/PDF paper models using Blender",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single file
  python inference.py --input model.obj --output model_unfolded.svg

  # Batch process all OBJ files in a folder
  python inference.py --input-dir models --output-dir output
        """
    )
    parser.add_argument('--input', help='Input OBJ file path')
    parser.add_argument('--output', help='Output SVG/PDF file path')
    parser.add_argument('--input-dir', help='Directory containing OBJ files for batch processing')
    parser.add_argument('--output-dir', default='output', help='Directory to save unfolded models (default: output)')
    parser.add_argument('--format', default='svg', choices=['svg', 'pdf'], help='Output format (svg or pdf, default: svg)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()

    if args.input_dir:
        process_batch(args.input_dir, args.output_dir, args.format, args.verbose)
    elif args.input and args.output:
        process_single(args.input, args.output, args.format, args.verbose)
    else:
        parser.error('You must specify either --input and --output for single file, or --input-dir for batch mode.')

if __name__ == "__main__":
    main()
