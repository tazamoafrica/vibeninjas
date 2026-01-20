import os
import re
from pathlib import Path


COLOR_REPLACEMENTS = {
    
    '#4f46e5': '#ff6b00',  
    '#4338ca': '#e05d00',  
    '#7c3aed': '#ff8c00',  
    'rgba(79, 70, 229,': 'rgba(255, 107, 0,',  
    'rgba(67, 56, 202,': 'rgba(224, 93, 0,',   
    'rgba(124, 58, 237,': 'rgba(255, 140, 0,',  
    '#3acd7a': '#ff6b00', 
    '#0fa158': '#ff6b00', 
    '#52bd84': '#ff8c00',
    '#29af6a': '#e05d00',
}


TEMPLATE_EXTENSIONS = ('.html', '.css', '.js')

# Directories to process
TEMPLATE_DIRS = [
    'events/templates',
    'static/css',
    'static/js',
]

def update_file_colors(file_path):
    """Update colors in a single file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Replace colors
        for old_color, new_color in COLOR_REPLACEMENTS.items():
            content = content.replace(old_color, new_color)
        
        # If content changed, write it back
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    base_dir = Path('.')
    updated_files = 0
    
    for template_dir in TEMPLATE_DIRS:
        template_path = base_dir / template_dir
        if not template_path.exists():
            continue
            
        for root, _, files in os.walk(template_path):
            for file in files:
                if file.endswith(TEMPLATE_EXTENSIONS):
                    file_path = Path(root) / file
                    if update_file_colors(file_path):
                        print(f"Updated: {file_path}")
                        updated_files += 1
    
    print(f"\nUpdated {updated_files} files with the new color scheme.")
    
    # Update theme.css if it exists
    theme_css = base_dir / 'static' / 'css' / 'theme.css'
    if theme_css.exists():
        with open(theme_css, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Ensure our theme variables are set correctly
        if ':root' in content:
            root_vars = """
:root {
    /* Primary Colors */
    --primary: #ff6b00;
    --primary-dark: #e05d00;
    --primary-light: #ff8c00;
    --primary-soft: rgba(255, 107, 0, 0.1);
    
    /* Text Colors */
    --text-primary: #1a1a1a;
    --text-secondary: #4b5563;
    --text-muted: #6b7280;
    
    /* Background Colors */
    --bg-light: #f9fafb;
    --bg-white: #ffffff;
    --bg-dark: #1f2937;
    
    /* Border Colors */
    --border-color: #e5e7eb;
    --border-dark: #d1d5db;
    
    /* Status Colors */
    --success: #10b981;
    --warning: #f59e0b;
    --danger: #ef4444;
    --info: #3b82f6;
}
"""
            with open(theme_css, 'w', encoding='utf-8') as f:
                f.write(root_vars + content.split(':root', 1)[1])
            print("\nUpdated theme.css with the new color scheme.")

if __name__ == '__main__':
    main()
