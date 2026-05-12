class MyFont:
    def __init__(self, size):
        if size == 'large':
            from font_large_data import FONT_LARGE_DATA
            self.width = 16
            self.height = 21
            self.font_data = FONT_LARGE_DATA
        elif size == 'small':
            from font_small_data import FONT_SMALL_DATA
            self.width = 12
            self.height = 16
            self.font_data = FONT_SMALL_DATA 
        else:
            raise ValueError("Invalid font size")
            
        self.bytes_per_col = (self.height + 7) // 8
        self.bytes_per_char = self.width * self.bytes_per_col
        self.space_data = b'\x00' * self.bytes_per_char

    def text(self, text, x, y, color=1, display=None):
        if display is None:
            return

        # Lokale Referenzen für Speed-Boost
        buf = display.buffer
        disp_w = display.width
        disp_h = display.height
        f_data = self.font_data
        f_width = self.width
        b_p_c = self.bytes_per_col
        s_data = self.space_data

        page_start = y // 8
        y_offset = y % 8
        page_end = (y + self.height - 1) // 8
        display_max_page = (disp_h // 8) - 1

        for char in str(text):
            # Fallback to space if character not found
            char_data = f_data.get(char, s_data)
            
            for char_col_idx in range(f_width):
                target_x = x + char_col_idx
                
                # Clipping: Prevent drawing outside horizontal bounds
                if target_x >= disp_w or target_x < 0:
                    continue
                    
                font_col_base = char_col_idx * b_p_c
                
                # Page-wise drawing
                for page in range(page_start, min(page_end + 1, display_max_page + 1)):
                    if page < 0: continue
                    
                    logical_idx = page - page_start
                    current_page_data = 0
                    
                    # 1. Main Part (Shift up)
                    if logical_idx < b_p_c:
                        font_byte = char_data[font_col_base + logical_idx]
                        current_page_data |= (font_byte << y_offset) & 0xFF
                    
                    # 2. Overflow (Shift down from previous byte)
                    if y_offset > 0 and logical_idx > 0:
                        prev_byte = char_data[font_col_base + logical_idx - 1]
                        current_page_data |= (prev_byte >> (8 - y_offset))

                    # Writing to display buffer
                    if current_page_data:
                        idx = page * disp_w + target_x
                        if color:
                            buf[idx] |= current_page_data
                        else:
                            buf[idx] &= ~current_page_data
            
            # Move to next character position
            x += f_width