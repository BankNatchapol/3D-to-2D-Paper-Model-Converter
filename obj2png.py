#!/usr/bin/env python3
"""
OBJ to PNG Renderer
Converts 3D OBJ files to high-quality PNG renders using Blender's bpy library.

This script provides a command-line interface for rendering OBJ files with
configurable lighting, camera settings, and output resolution.

Usage:
    # Single file processing
    python obj2png.py <input_obj_path> <output_png_path> [options]
    
    # Batch processing
    python obj2png.py --input-dir <input_directory> --output-dir <output_directory> [options]
    
Examples:
    python obj2png.py models/cube.obj output/cube_render.png
    python obj2png.py models/complex.obj output/complex.png --resolution 4k --engine cycles
    python obj2png.py --input-dir models/ --output-dir renders/ --resolution FHD
"""

import bpy
import os
import sys
import argparse
import logging
from math import radians
from pathlib import Path
import math
from mathutils import Vector
import glob

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

class OBJRenderer:
    """Handles rendering of OBJ files to PNG using Blender's bpy library."""
    
    def __init__(self, render_engine='CYCLES', resolution='HD'):
        """
        Initialize the OBJ renderer.
        
        Args:
            render_engine (str): Rendering engine ('CYCLES' or 'BLENDER_EEVEE_NEXT')
            resolution (str): Resolution preset ('HD', 'FHD', '4K', '8K')
        """
        # Map user-friendly names to Blender 4.4 enum values
        engine_mapping = {
            'cycles': 'CYCLES',
            'eevee': 'BLENDER_EEVEE_NEXT',
            'CYCLES': 'CYCLES',
            'BLENDER_EEVEE_NEXT': 'BLENDER_EEVEE_NEXT'
        }
        
        self.render_engine = engine_mapping.get(render_engine.upper(), 'CYCLES')
        self.resolution_presets = {
            'HD': (1280, 720),
            'FHD': (1920, 1080),
            '4K': (3840, 2160),
            '8K': (7680, 4320)
        }
        self.resolution = self.resolution_presets.get(resolution.upper(), (1920, 1080))
        
    def setup_scene(self):
        """Configure Blender scene for rendering."""
        try:
            logger.info("Setting up Blender scene...")
            
            # Clear existing objects
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

            # Configure render settings
            scene = bpy.context.scene
            scene.render.engine = self.render_engine
            scene.render.image_settings.file_format = 'PNG'
            scene.render.resolution_x = self.resolution[0]
            scene.render.resolution_y = self.resolution[1]
            scene.render.resolution_percentage = 100
            
            logger.info(f"Scene configured: {self.render_engine} engine, {self.resolution[0]}x{self.resolution[1]} resolution")
            
        except Exception as e:
            raise RuntimeError(f"Failed to setup scene: {e}")
    
    def import_obj(self, obj_path):
        """
        Import OBJ file into the scene.
        
        Args:
            obj_path (str): Path to the OBJ file
            
        Returns:
            bpy.types.Object: The imported object
        """
        if not os.path.exists(obj_path):
            raise FileNotFoundError(f"OBJ file not found: {obj_path}")
        
        logger.info(f"Importing OBJ file: {obj_path}")
        
        try:
bpy.ops.wm.obj_import(
                filepath=obj_path,
                filter_glob="*.obj;*.mtl"
            )
            
            # Get the imported object
            imported = bpy.context.selected_objects
            if not imported:
                raise RuntimeError(f"No objects imported from {obj_path}")
            
            obj = imported[0]
            logger.info(f"✓ Imported object: {obj.name}")
            return obj
            
        except Exception as e:
            raise RuntimeError(f"Failed to import OBJ file: {e}")
    
    def setup_camera(self, target_object=None, margin=2.5):
        """
        Set up camera to automatically frame the target object.
        
        Args:
            target_object: The object to frame (if None, uses the first mesh object)
            margin (float): Margin factor around the object (1.0 = tight fit, 2.5 = 150% margin)
        """
        try:
            logger.info("Setting up camera with automatic framing...")
            
            scene = bpy.context.scene
            
            # Create camera
cam_data = bpy.data.cameras.new("Camera")
            cam_obj = bpy.data.objects.new("Camera", cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj
            
            # If no target object specified, use the first mesh object
            if target_object is None:
                mesh_objects = [obj for obj in scene.objects if obj.type == 'MESH']
                if not mesh_objects:
                    raise RuntimeError("No mesh objects found in scene")
                target_object = mesh_objects[0]
            
            # Calculate object bounding box
            bbox_corners = []
            for vertex in target_object.bound_box:
                world_vertex = target_object.matrix_world @ Vector(vertex)
                bbox_corners.append(world_vertex)
            
            # Calculate bounding box dimensions
            min_x = min(v[0] for v in bbox_corners)
            max_x = max(v[0] for v in bbox_corners)
            min_y = min(v[1] for v in bbox_corners)
            max_y = max(v[1] for v in bbox_corners)
            min_z = min(v[2] for v in bbox_corners)
            max_z = max(v[2] for v in bbox_corners)
            
            # Calculate object center and size
            center_x = (min_x + max_x) / 2
            center_y = (min_y + max_y) / 2
            center_z = (min_z + max_z) / 2
            size_x = max_x - min_x
            size_y = max_y - min_y
            size_z = max_z - min_z
            
            # Calculate the maximum dimension for framing
            max_dimension = max(size_x, size_y, size_z)
            
            # Use a 45-degree field of view for a wider shot
            fov_radians = radians(45)
            camera_distance = (max_dimension * margin) / (2 * math.tan(fov_radians / 2))
            camera_distance = max(camera_distance, 3.0)

            # Lower elevation for more horizontal view (floor visible)
            angle_x = radians(35)
            angle_z = radians(-65)

            cam_x = center_x + camera_distance * math.cos(angle_x) * math.cos(angle_z)
            cam_y = center_y + camera_distance * math.cos(angle_x) * math.sin(angle_z)
            cam_z = center_z + camera_distance * math.sin(angle_x)

            cam_obj.location = (cam_x, cam_y, cam_z)
            direction = (center_x - cam_x, center_y - cam_y, center_z - cam_z)
            rot_quat = self.direction_to_rotation(direction)
            
            cam_obj.rotation_euler = rot_quat.to_euler()
            cam_data.lens = 35.0

            logger.info(f"✓ Camera configured: distance={camera_distance:.2f}, object_size={max_dimension:.2f}, margin={margin}")
            
        except Exception as e:
            raise RuntimeError(f"Failed to setup camera: {e}")

    def direction_to_rotation(self, direction):
        """Convert a direction vector to a rotation quaternion."""
        from mathutils import Vector, Quaternion
        
        # Normalize the direction vector
        direction = Vector(direction).normalized()
        
        # Create a rotation that points the negative Z axis (camera forward) toward the direction
        z_axis = Vector((0, 0, -1))
        rotation = z_axis.rotation_difference(direction)
        
        return rotation
    
    def setup_lighting(self, energy=1000):
        """
        Set up lighting for the scene.
        
        Args:
            energy (float): Light energy/intensity
        """
        try:
            logger.info("Setting up lighting...")
            
            scene = bpy.context.scene
            
            # Create area light
light_data = bpy.data.lights.new(name="AreaLight", type='AREA')
            light_data.energy = energy
light_obj = bpy.data.objects.new(name="AreaLight", object_data=light_data)
scene.collection.objects.link(light_obj)
light_obj.location = (4.0, -4.0, 6.0)

            # Add fill light
            fill_light_data = bpy.data.lights.new(name="FillLight", type='AREA')
            fill_light_data.energy = energy * 0.3
            fill_light_obj = bpy.data.objects.new(name="FillLight", object_data=fill_light_data)
            scene.collection.objects.link(fill_light_obj)
            fill_light_obj.location = (-4.0, 4.0, 3.0)
            
            logger.info("✓ Lighting configured")
            
        except Exception as e:
            raise RuntimeError(f"Failed to setup lighting: {e}")
    
    def render(self, output_path):
        """
        Render the scene to PNG.
        
        Args:
            output_path (str): Output path for the PNG file
            
        Returns:
            str: Path to the rendered file
        """
        try:
            # Convert to absolute path for Blender
            if not os.path.isabs(output_path):
                output_path = os.path.abspath(output_path)
            
            # Ensure output directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # Set render output path (Blender needs absolute path)
            bpy.context.scene.render.filepath = output_path
            
            logger.info(f"Rendering to: {output_path}")
            
            # Render
            bpy.ops.render.render(write_still=True)
            
            if os.path.exists(output_path):
                logger.info(f"✓ Render completed: {output_path}")
                return output_path
            else:
                raise RuntimeError(f"Render failed - file not created: {output_path}")
                
        except Exception as e:
            raise RuntimeError(f"Failed to render: {e}")

    def process_single(self, input_path, output_path):
        """
        Process a single OBJ file.
        
        Args:
            input_path (str): Path to input OBJ file
            output_path (str): Path for output PNG file
            
        Returns:
            str: Path to the rendered file
        """
        # Setup scene
        self.setup_scene()
        
        # Import OBJ
        obj = self.import_obj(input_path)
        
        # Setup camera and lighting
        self.setup_camera(target_object=obj)
        self.setup_lighting()
        
        # Render
        return self.render(output_path)

    def process_batch(self, input_dir, output_dir):
        """
        Process all OBJ files in a directory.
        
        Args:
            input_dir (str): Directory containing OBJ files
            output_dir (str): Directory to save rendered PNG files
            
        Returns:
            list: List of successfully processed files
        """
        if not os.path.exists(input_dir):
            raise FileNotFoundError(f"Input directory not found: {input_dir}")
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Find all OBJ files in input directory
        obj_files = glob.glob(os.path.join(input_dir, "*.obj"))
        
        if not obj_files:
            logger.warning(f"No OBJ files found in {input_dir}")
            return []
        
        logger.info(f"Found {len(obj_files)} OBJ files to process")
        
        successful_renders = []
        
        for obj_file in obj_files:
            try:
                # Generate output filename
                base_name = os.path.splitext(os.path.basename(obj_file))[0]
                output_file = os.path.join(output_dir, f"{base_name}.png")
                
                logger.info(f"\n--- Processing: {os.path.basename(obj_file)} ---")
                
                # Process the file
                rendered_file = self.process_single(obj_file, output_file)
                successful_renders.append(rendered_file)
                
                logger.info(f"✓ Successfully rendered: {os.path.basename(rendered_file)}")
                
            except Exception as e:
                logger.error(f"Failed to process {obj_file}: {e}")
                continue
        
        logger.info(f"\nBatch processing complete: {len(successful_renders)}/{len(obj_files)} files processed successfully")
        return successful_renders

def main():
    """Main function to handle command line arguments and process the rendering."""
    parser = argparse.ArgumentParser(
        description='Convert OBJ file(s) to high-quality PNG render(s)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Single file processing
    python obj2png.py models/cube.obj output/cube_render.png
    python obj2png.py models/complex.obj output/complex.png --resolution 4k --engine cycles
    
    # Batch processing
    python obj2png.py --input-dir models/ --output-dir renders/ --resolution FHD
    python obj2png.py --input-dir models/ --output-dir renders/ --engine eevee --quality fast
        """
    )
    
    # Create mutually exclusive group for single vs batch processing
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--input-dir', 
                      help='Directory containing OBJ files for batch processing')
    group.add_argument('input_obj', nargs='?',
                      help='Path to input OBJ file (for single file processing)')
    
    parser.add_argument('output_png', nargs='?',
                       help='Path for output PNG file (for single file processing)')
    parser.add_argument('--output-dir',
                       help='Directory for output PNG files (for batch processing)')
    parser.add_argument('--engine', '-e',
                       choices=['cycles', 'eevee'],
                       default='cycles',
                       help='Rendering engine: cycles (photorealistic) or eevee (fast, default: cycles)')
    parser.add_argument('--resolution', '-r',
                       choices=['HD', 'FHD', '4K', '8K'],
                       default='FHD',
                       help='Output resolution (default: FHD)')
    parser.add_argument('--quality', '-q',
                       choices=['fast', 'medium', 'high'],
                       default='medium',
                       help='Render quality (default: medium)')
    parser.add_argument('--verbose', '-v',
                       action='store_true',
                       help='Enable verbose output')
    
    # Parse arguments
    if len(sys.argv) == 1:
        parser.print_help()
        return 1
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.input_dir:
        # Batch processing mode
        if not args.output_dir:
            parser.error("--output-dir is required when using --input-dir")
    else:
        # Single file processing mode
        if not args.input_obj or not args.output_png:
            parser.error("Both input_obj and output_png are required for single file processing")
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Initialize renderer
        renderer = OBJRenderer(
            render_engine=args.engine,
            resolution=args.resolution
        )
        
        if args.input_dir:
            # Batch processing
            logger.info(f"Starting batch processing...")
            logger.info(f"Input directory: {args.input_dir}")
            logger.info(f"Output directory: {args.output_dir}")
            logger.info(f"Engine: {args.engine.upper()}")
            logger.info(f"Resolution: {args.resolution}")
            
            successful_renders = renderer.process_batch(args.input_dir, args.output_dir)
            
            print(f"\n🎨 Batch processing complete!")
            print(f"   Successfully rendered: {len(successful_renders)} files")
            print(f"   Output directory: {args.output_dir}")
            
        else:
            # Single file processing
            logger.info(f"Processing single file: {args.input_obj}")
            
            output_file = renderer.process_single(args.input_obj, args.output_png)
            
            print(f"\n🎨 Success! Rendered image created: {output_file}")
            print(f"   Engine: {args.engine.upper()}")
            print(f"   Resolution: {args.resolution} ({renderer.resolution[0]}x{renderer.resolution[1]})")
        
        return 0
        
    except Exception as e:
        logger.error(f"Rendering failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
