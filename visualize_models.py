#!/usr/bin/env python3
"""
3D Model Visualizer
Creates comparison visualizations between 3D renders and paper models.

This script converts PDF paper models to PNG images and creates side-by-side
comparisons with their corresponding 3D renders for easy visual analysis.

Usage:
    python visualize_models.py [options]
    
Examples:
    python visualize_models.py --input-dir models --output-dir output
    python visualize_models.py --3d-renders "render1.png,render2.png" --paper-models "model1.pdf,model2.pdf"
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.backends.backend_pdf import PdfPages
import fitz  # PyMuPDF
import cairosvg
import io
from PIL import Image

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

class ModelVisualizer:
    """Convert paper models to PNG and create side-by-side comparisons with 3D renders."""
    
    def __init__(self, input_dir: str = "output", output_dir: str = "comparisons"):
        """
        Initialize the visualizer.
        
        Args:
            input_dir: Directory containing both 3D render PNG files and paper model PDF/SVG files
            output_dir: Directory to save comparison images
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        
        # Create output directory if it doesn't exist
        self.output_dir.mkdir(exist_ok=True)
        
        # Supported file extensions
        self.render_extensions = {'.png', '.jpg', '.jpeg'}
        self.paper_extensions = {'.pdf', '.svg'}
        
    def find_file_pairs(self) -> Dict[str, Tuple[Path, Path]]:
        """
        Find pairs of files where one has base name and other has '_unfolded' appended.
        
        Returns:
            Dictionary mapping base names to (render_file, paper_file) tuples
        """
        pairs = {}
        
        if not self.input_dir.exists():
            logger.error(f"Input directory not found: {self.input_dir}")
            return pairs
        
        # Get all render files
        render_files = {}
        for ext in self.render_extensions:
            for f in self.input_dir.glob(f"*{ext}"):
                render_files[f.stem] = f
                logger.debug(f"Found render file: {f.name}")
        
        # Get all paper model files
        paper_files = {}
        for ext in self.paper_extensions:
            for f in self.input_dir.glob(f"*{ext}"):
                # Check if this is an "_unfolded" file
                if f.stem.endswith('_unfolded'):
                    base_name = f.stem[:-9]  # Remove '_unfolded' suffix (9 characters)
                    paper_files[base_name] = f
                    logger.debug(f"Found paper model file: {f.name} -> base: {base_name}")
                else:
                    logger.debug(f"Found paper model file (no _unfolded suffix): {f.name}")
        
        # Also check for PNG paper model files (converted versions)
        for f in self.input_dir.glob("*_unfolded.png"):
            base_name = f.stem[:-9]  # Remove '_unfolded' suffix (9 characters)
            paper_files[base_name] = f
            logger.debug(f"Found PNG paper model file: {f.name} -> base: {base_name}")
        
        logger.info(f"Found {len(render_files)} render files and {len(paper_files)} paper model files")
        
        # Find matching pairs
        for base_name in render_files:
            if base_name in paper_files:
                pairs[base_name] = (render_files[base_name], paper_files[base_name])
                logger.info(f"✓ Found pair: {base_name} -> {render_files[base_name].name} + {paper_files[base_name].name}")
            else:
                logger.debug(f"✗ No paper model found for render: {base_name}")
        
        # Log unmatched files
        unmatched_renders = set(render_files.keys()) - set(pairs.keys())
        unmatched_papers = set(paper_files.keys()) - set(pairs.keys())
        
        if unmatched_renders:
            logger.warning(f"Unmatched render files: {', '.join(sorted(unmatched_renders))}")
        if unmatched_papers:
            logger.warning(f"Unmatched paper model files: {', '.join(sorted(unmatched_papers))}")
        
        return pairs
    
    def convert_pdf_to_png(self, pdf_path: Path, output_path: Path, dpi: int = 300) -> bool:
        """Convert PDF to PNG using PyMuPDF."""
        try:
            doc = fitz.open(str(pdf_path))
            if len(doc) == 0:
                logger.error(f"PDF {pdf_path} has no pages")
                return False
            
            # Get first page
            page = doc[0]
            mat = fitz.Matrix(dpi/72, dpi/72)  # Scale factor for DPI
            pix = page.get_pixmap(matrix=mat)
            
            # Save as PNG
            pix.save(str(output_path))
            doc.close()
            return True
            
        except Exception as e:
            logger.error(f"Error converting PDF {pdf_path}: {e}")
            return False
    
    def convert_svg_to_png(self, svg_path: Path, output_path: Path, dpi: int = 300) -> bool:
        """Convert SVG to PNG using cairosvg."""
        try:
            # Convert SVG to PNG
            png_data = cairosvg.svg2png(
                url=str(svg_path),
                dpi=dpi,
                output_width=None,
                output_height=None
            )
            
            # Save PNG data
            with open(output_path, 'wb') as f:
                f.write(png_data)
            
            return True
            
        except Exception as e:
            logger.error(f"Error converting SVG {svg_path}: {e}")
            return False
    
    def convert_paper_model_to_png(self, paper_path: Path, output_path: Path, dpi: int = 300) -> bool:
        """Convert paper model (PDF or SVG) to PNG, or use image directly if already PNG/JPG/JPEG."""
        ext = paper_path.suffix.lower()
        if ext in ['.pdf']:
            return self.convert_pdf_to_png(paper_path, output_path, dpi)
        elif ext in ['.svg']:
            return self.convert_svg_to_png(paper_path, output_path, dpi)
        elif ext in ['.png', '.jpg', '.jpeg']:
            # Already an image, just copy or use directly
            if paper_path.resolve() == output_path.resolve():
                # Already at the output path
                return True
            try:
                from shutil import copyfile
                copyfile(paper_path, output_path)
                return True
            except Exception as e:
                logger.error(f"Error copying image paper model {paper_path}: {e}")
                return False
        else:
            logger.error(f"Unsupported paper model format: {paper_path.suffix}")
            return False
    
    def create_comparison(self, base_name: str, render_path: Path, paper_path: Path, 
                         dpi: int = 300) -> Optional[Path]:
        """Create a side-by-side comparison of render and paper model."""
        try:
            # If paper model is already an image, use it directly
            ext = paper_path.suffix.lower()
            if ext in ['.png', '.jpg', '.jpeg']:
                temp_paper_png = paper_path
            else:
                # Convert paper model to PNG
                temp_paper_png = self.output_dir / f"{base_name}_paper_temp.png"
                if not self.convert_paper_model_to_png(paper_path, temp_paper_png, dpi):
                    return None

            # Load images
            render_img = mpimg.imread(str(render_path))
            paper_img = mpimg.imread(str(temp_paper_png))
            
            # Create figure with subplots
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
            
            # Display render
            ax1.imshow(render_img)
            ax1.set_title(f'3D Render: {render_path.name}', fontsize=14, fontweight='bold')
            ax1.axis('off')
            
            # Display paper model
            ax2.imshow(paper_img)
            ax2.set_title(f'Paper Model: {paper_path.name}', fontsize=14, fontweight='bold')
            ax2.axis('off')
            
            # Add overall title
            fig.suptitle(f'Model Comparison: {base_name}', fontsize=16, fontweight='bold')
            
            # Save comparison
            output_path = self.output_dir / f"{base_name}_comparison.png"
            plt.savefig(output_path, dpi=dpi, bbox_inches='tight', pad_inches=0.5)
            plt.close()
            
            # Clean up temporary file if we created one
            if ext not in ['.png', '.jpg', '.jpeg']:
                temp_paper_png.unlink(missing_ok=True)
            
            logger.info(f"Created comparison: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error creating comparison for {base_name}: {e}")
            return None
    
    def create_summary_pdf(self, comparison_paths: List[Path], output_path: Path) -> bool:
        """Create a PDF with all comparisons."""
        try:
            with PdfPages(output_path) as pdf:
                for comp_path in comparison_paths:
                    if comp_path.exists():
                        img = mpimg.imread(str(comp_path))
                        fig, ax = plt.subplots(figsize=(16, 8))
                        ax.imshow(img)
                        ax.axis('off')
                        pdf.savefig(fig, bbox_inches='tight', pad_inches=0.5)
                        plt.close()
            
            logger.info(f"Created summary PDF: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating summary PDF: {e}")
            return False
    
    def process_all(self, dpi: int = 300, create_summary: bool = True) -> List[Path]:
        """
        Process all file pairs and create comparisons.
        
        Args:
            dpi: Resolution for conversions
            create_summary: Whether to create a summary PDF
            
        Returns:
            List of created comparison file paths
        """
        logger.info("Starting model visualization process...")
        
        # Find file pairs
        pairs = self.find_file_pairs()
        
        if not pairs:
            logger.warning("No matching file pairs found!")
            return []
        
        logger.info(f"Found {len(pairs)} file pairs to process")
        
        # Process each pair
        comparison_paths = []
        for base_name, (render_path, paper_path) in pairs.items():
            logger.info(f"Processing pair: {base_name}")
            
            comparison_path = self.create_comparison(base_name, render_path, paper_path, dpi)
            if comparison_path:
                comparison_paths.append(comparison_path)
        
        # Create summary PDF if requested
        if create_summary and comparison_paths:
            summary_path = self.output_dir / "all_comparisons.pdf"
            self.create_summary_pdf(comparison_paths, summary_path)
        
        logger.info(f"Completed! Created {len(comparison_paths)} comparisons")
        return comparison_paths

def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Convert paper models to PNG and create side-by-side comparisons with 3D renders",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all files with default settings
  python visualize_models.py
  
  # Specify custom input directory
  python visualize_models.py --input-dir models --output-dir comparisons
  
  # High resolution output
  python visualize_models.py --dpi 600
  
  # Process specific files only
  python visualize_models.py --render-files model1.png model2.png --paper-files model1_unfolded.pdf model2_unfolded.svg
        """
    )
    
    parser.add_argument('--input-dir', default='output',
                       help='Directory containing both 3D render PNG files and paper model PDF/SVG files (default: output)')
    parser.add_argument('--output-dir', default='comparisons',
                       help='Directory to save comparison images (default: comparisons)')
    parser.add_argument('--dpi', type=int, default=300,
                       help='Resolution for conversions (default: 300)')
    parser.add_argument('--no-summary', action='store_true',
                       help='Skip creating summary PDF')
    parser.add_argument('--render-files', nargs='+',
                       help='Specific render files to process (overrides input-dir)')
    parser.add_argument('--paper-files', nargs='+',
                       help='Specific paper model files to process (overrides input-dir)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create visualizer
    visualizer = ModelVisualizer(args.input_dir, args.output_dir)
    
    # Handle specific file processing
    if args.render_files and args.paper_files:
        if len(args.render_files) != len(args.paper_files):
            logger.error("Number of render files must match number of paper files")
            sys.exit(1)
        
        # Create temporary pairs for specific files
        pairs = {}
        for render_file, paper_file in zip(args.render_files, args.paper_files):
            render_path = Path(render_file)
            paper_path = Path(paper_file)
            
            if not render_path.exists():
                logger.error(f"Render file not found: {render_path}")
                continue
            if not paper_path.exists():
                logger.error(f"Paper file not found: {paper_path}")
                continue
            
            # Extract base name from render file
            base_name = render_path.stem
            pairs[base_name] = (render_path, paper_path)
        
        # Override the find_file_pairs method temporarily
        visualizer.find_file_pairs = lambda: pairs
    
    # Process files
    try:
        comparison_paths = visualizer.process_all(
            dpi=args.dpi,
            create_summary=not args.no_summary
        )
        
        if comparison_paths:
            print(f"\n✅ Successfully created {len(comparison_paths)} comparisons:")
            for path in comparison_paths:
                print(f"  - {path}")
        else:
            print("\n❌ No comparisons were created. Check the logs for details.")
            
    except KeyboardInterrupt:
        print("\n⚠️  Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 