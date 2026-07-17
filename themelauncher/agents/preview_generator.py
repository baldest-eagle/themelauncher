"""
Preview Generator Agent — generates UI preview images from .msstyles and .theme files.
Enhanced with pefile for resource extraction.
"""

import os
import configparser
import io
from PIL import Image, ImageDraw
import pefile

from core.logger import log

class PreviewGenerator:
    def __init__(self, output_size=(160, 107)):
        self.output_size = output_size

    def generate_from_theme(self, theme_path: str, output_path: str) -> bool:
        """Parse a .theme file and generate a preview image."""
        try:
            config = configparser.ConfigParser(interpolation=None)
            
            # Read as binary to handle BOM and encoding more safely
            with open(theme_path, 'rb') as f:
                raw_data = f.read()

            # Try to decode
            content = None
            for enc in ['utf-16', 'utf-16-le', 'utf-16-be', 'utf-8-sig', 'utf-8', 'cp1252']:
                try:
                    content = raw_data.decode(enc)
                    if '[' in content and ']' in content: # Basic INI check
                        break
                    content = None
                except (UnicodeDecodeError, UnicodeError):
                    continue
            
            if not content:
                log.error("Could not decode theme file correctly: %s", theme_path)
                return False
                
            config.read_string(content)

            # Get wallpaper
            wallpaper = config.get('Control Panel\\Desktop', 'Wallpaper', fallback=None)
            
            # Generate image
            img = Image.new('RGB', self.output_size, color='#2b2b2b')
            draw = ImageDraw.Draw(img)

            if wallpaper and os.path.exists(wallpaper):
                try:
                    wp_img = Image.open(wallpaper)
                    wp_img.thumbnail(self.output_size, Image.LANCZOS)
                    offset = ((self.output_size[0] - wp_img.width) // 2,
                              (self.output_size[1] - wp_img.height) // 2)
                    img.paste(wp_img, offset)
                except Exception:
                    pass

            self._draw_simulated_ui(draw)
            img.save(output_path)
            return True
        except Exception as e:
            log.error("Failed to generate preview from theme: %s", e)
            return False

    def generate_from_msstyles(self, msstyles_path: str, output_path: str) -> bool:
        """Generate a preview from an .msstyles file using resource extraction."""
        try:
            img = Image.new('RGB', self.output_size, color='#3d3d3d')
            draw = ImageDraw.Draw(img)
            
            # Draw window frame
            draw.rectangle([10, 10, 150, 97], outline="#555555", width=1)
            draw.rectangle([10, 10, 150, 30], fill="#2b2b2b") # Titlebar
            
            # Try to extract actual caption buttons
            buttons = self.extract_caption_buttons(msstyles_path)
            
            if buttons and 'close' in buttons:
                # Paste close button
                cbtn = buttons['close'].resize((12, 12), Image.LANCZOS)
                img.paste(cbtn, (135, 14), cbtn if cbtn.mode == 'RGBA' else None)
            else:
                # Fallback to simulated
                draw.rectangle([135, 15, 145, 25], fill="#e81123")
                
            if buttons and 'max' in buttons:
                mbtn = buttons['max'].resize((12, 12), Image.LANCZOS)
                img.paste(mbtn, (120, 14), mbtn if mbtn.mode == 'RGBA' else None)
            else:
                draw.rectangle([120, 15, 130, 25], outline="#ffffff", width=1)

            img.save(output_path)
            return True
        except Exception as e:
            log.error("Failed to generate preview from msstyles: %s", e)
            return False

    def extract_caption_buttons(self, msstyles_path: str) -> dict:
        """Use pefile to extract bitmap resources from .msstyles with broad heuristics."""
        results = {}
        candidates = []
        try:
            pe = pefile.PE(msstyles_path)
            if hasattr(pe, 'DIRECTORY_ENTRY_RESOURCE'):
                for resource_type in pe.DIRECTORY_ENTRY_RESOURCE.entries:
                    if resource_type.name is not None:
                        type_name = str(resource_type.name)
                    else:
                        type_name = pefile.RESOURCE_TYPE.get(resource_type.struct.Id, str(resource_type.struct.Id))
                    
                    if type_name in ('IMAGE', 'BITMAP', 'PNG', '10'): # 10 is often IMAGE
                        for resource_id in resource_type.directory.entries:
                            for resource_lang in resource_id.directory.entries:
                                data = pe.get_data(resource_lang.data.struct.OffsetToData, resource_lang.data.struct.Size)
                                try:
                                    res_img = Image.open(io.BytesIO(data))
                                    # Heuristic: button strips are wider than they are tall
                                    # Standard strips are usually 15-40px high and 100-500px wide
                                    if 10 < res_img.height < 60 and res_img.width > res_img.height * 3:
                                        candidates.append(res_img)
                                except Exception:
                                    continue

            # Sort candidates: we want those that likely contain the 'Close' button
            # 'Close' buttons often have red in them in modern styles
            for res_img in candidates:
                # Simple check: does it have a 'Close' feel? 
                # (This is hard, so we'll just try to find the most likely strip)
                # Usually the caption buttons are among the first 20 images
                seg_width = res_img.height # Assumption: square segments
                if res_img.width % seg_width == 0 or res_img.width % (seg_width + 1) == 0:
                    # Very likely a button strip
                    results['close'] = res_img.crop((0, 0, seg_width, res_img.height))
                    # Max is usually the next strip or further down the same strip
                    # In many strips, it's [Normal, Hover, Pressed, Disabled...]
                    # But sometimes it's [Min, Max, Close...]
                    # We'll take a second segment as a 'Max' guess
                    if res_img.width >= seg_width * 2:
                         results['max'] = res_img.crop((seg_width, 0, seg_width*2, res_img.height))
                    break # Take the first good one

            pe.close()
        except Exception as e:
            log.debug("Resource extraction failed (pefile): %s", e)
        return results

    def _draw_simulated_ui(self, draw):
        """Draw a tiny mock-up of Windows UI elements."""
        draw.rectangle([0, 90, 160, 107], fill="#1a1a1a") # Taskbar
        draw.ellipse([5, 93, 15, 103], fill="#0078d7") # Start
        draw.rectangle([20, 104, 40, 106], fill="#0078d7") # App line
