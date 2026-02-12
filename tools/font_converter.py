import math
# import both raw data sets from raw_font.py 
from raw_font import FONT_LARGE_RAW, FONT_SMALL_RAW 

# --- Parameter for LARGE Font ---
LARGE_WIDTH = 16
LARGE_HEIGHT = 21

# --- Parameter for SMALL Font ---
SMALL_WIDTH = 12
SMALL_HEIGHT = 16

# --- 1. conversion ---
def _pixels_to_mono_vlsb(pixels, w, h):
    bytes_per_column = (h + 7) // 8 
    buf = bytearray(w * bytes_per_column)
    
    # 1. create VLSB-buffer
    for y in range(h):
        for x in range(w):
            
            if pixels[y * w + x]:
                
                # VLSB-adress: Page (y // 8) und row (x)
                byte_idx = x * bytes_per_column + (y // 8)
                bit = y % 8
                
                # set bit
                buf[byte_idx] |= (1 << bit)
    
    return bytes(buf) 

# --- 2. main logic for generation ---
def generate_font_data(raw_data, w, h):
    converted_data = {}
    for char, pixels in raw_data.items():
        if len(pixels) == w * h:
            converted_data[char] = _pixels_to_mono_vlsb(pixels, w, h)
        else:
            print(f"Error at {char}: wrong pixel no ({len(pixels)}), expected {w * h}")
            converted_data[char] = b'' 
    return converted_data

# --- 3. store data in *.py file ---
def save_font_data(data, filename, var_name):
    with open(filename, 'w') as f:
        f.write(f"# automatic generated Font data\n")
        f.write(f"{var_name} = {{\n")
        
        for char, bin_data in data.items():
            hex_escaped = "".join([f"\\x{b:02x}" for b in bin_data])
            
            BLOCK_SIZE = 16 * 4 # 16 Bytes per line 
            hex_blocks = [hex_escaped[i:i + BLOCK_SIZE] for i in range(0, len(hex_escaped), BLOCK_SIZE)]
            
            f.write(f"    '{char}': b'")
            f.write("'\n          b'".join(hex_blocks))
            f.write("',\n")
            
        f.write("}\n")
    print(f"Success: data stored in {filename}")


if __name__ == "__main__":
    
    # --- 1. LARGE FONT GENERATION ---
    print("Start conversion for LARGE Font...")
    large_data = generate_font_data(FONT_LARGE_RAW, LARGE_WIDTH, LARGE_HEIGHT)
    save_font_data(large_data, 'font_large_data.py', 'FONT_LARGE_DATA')
    
    # --- 2. SMALL FONT GENERATION ---
    print("Start conversion for SMALL Font...")
    small_data = generate_font_data(FONT_SMALL_RAW, SMALL_WIDTH, SMALL_HEIGHT)
    save_font_data(small_data, 'font_small_data.py', 'FONT_SMALL_DATA')
    
    print("\nConversion for both fonts finished")