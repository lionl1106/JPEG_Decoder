class JPEG_Decoder:
    def __init__(self, file_path):
        self.image_info = {}
        self.quantization_tables, self.huffman_tables = {}, {}
        with open(file_path, 'rb') as file:
            self.data = list(map(int, file.read()))

        self.pos, self.end = 0, len(self.data)
        self.bit_pos = -1

    def Get_bit(self):
        if self.bit_pos / 8 == self.end : raise RuntimeError("Out of file")
        if self.bit_pos == -1 : self.bit_pos = self.pos << 3
            
        prev_byte, curr_byte = self.data[(self.bit_pos >> 3) - 1], self.data[self.bit_pos >> 3]
        # Replace 0xFF00 to 0xFF
        if prev_byte == 0xFF and curr_byte == 0x00:
            self.bit_pos += 8
            prev_byte, curr_byte = curr_byte, self.data[self.bit_pos >> 3]
            
        shift = 7 - (self.bit_pos & 7)
        self.bit_pos += 1
        return (curr_byte >> shift) & 1
        
    def Get_bytes(self, length):
        if self.pos == self.end : raise RuntimeError("Out of file")
        self.pos += length

        if length == 0 : return 0
        if length == 1 : return self.data[self.pos - length]
        return self.data[self.pos - length : self.pos]

    def Huffman_Decode(self, huffman_table):
        result = []
        code = ""
        while code not in huffman_table:
            code += str(self.Get_bit())
            
        symbol = huffman_table[code]
        #print(f'code = {code}, symbol = {symbol}')
        return symbol

    def Parse(self):
        huffman_tables, quantization_tables = {}, {}
        [prev, curr] = self.Get_bytes(2)
        while self.pos != self.end + 1:
            code = prev << 8 | curr
            #print(format(curr, 'x'), end=' ')
            match code:
                case 0xFFD8:
                    print(format(code, 'x'), 'Start of the image')
                case 0xFFDB:
                    print(format(code, 'x'), 'Quantization tables')
                    self.DQT_Process()
                case 0xFFC4:
                    print(format(code, 'x'), 'Huffman tables')
                    self.DHT_Process()
                case 0xFFC0:
                    print(format(code, 'x'), 'Image structures')
                    self.SOF_Process()
                case 0xFFDA:
                    print(format(code, 'x'), 'Start of decompressing')
                    self.SOS_Process()
                case 0xFFD9:
                    print(format(code, 'x'), 'End of the image')
                    break
                case _:
                    pass
                    
            prev, curr = curr, self.Get_bytes(1)

    def SOF_Process(self):
        # Read length
        length = self.Get_bytes(1) << 8 | self.Get_bytes(1)
        print(f'SOF sequence length = {length}')
    
        self.image_info = {
            'precision': self.Get_bytes(1),
            'height': self.Get_bytes(1) << 8 | self.Get_bytes(1),
            'width':  self.Get_bytes(1) << 8 | self.Get_bytes(1),
            'num_components': self.Get_bytes(1),
            'components': []
        }

        # Extract component information
        length -= 8
        while length:
            length -= 3
            component_id = self.Get_bytes(1)
            sampling_factors = self.Get_bytes(1)
            h_sampling = sampling_factors >> 4
            v_sampling = sampling_factors & 0x0F
            quant_table_selector = self.Get_bytes(1)
            
            self.image_info['components'].append({
                'id': component_id,
                'h_factor': h_sampling,
                'v_factor': v_sampling,
                'quant_table': quant_table_selector
            })

    def DQT_Process(self):
        # Read length
        length = self.Get_bytes(1) << 8 | self.Get_bytes(1)
        print(f'DQT sequence length = {length}')
        
        # Start decoding tables
        length -= 2
        while length:
            # Read Table Information
            length -= 1
            byte = self.Get_bytes(1)
            precision, table_id = (byte & 0xF0) >> 4, byte & 0x0F
            
            # Read Quantization Table
            if precision == 0:
                length -= 64
                self.quantization_tables[table_id] = self.Get_bytes(64)
            elif precision == 1:
                length -= 128
                tmp = self.Get_bytes(128)
                self.quantization_tables[table_id] = [tmp[i] << 8 | tmp[i + 1] for i in range(0, 128, 2)]
            else:
                raise ValueError("Unsupported precision")
        
    def DHT_Process(self):
        # Read length
        length = self.Get_bytes(1) << 8 | self.Get_bytes(1)
        print(f'DHT sequence length = {length}')
        
        # Start decoding tables
        length -= 2
        while length:
            # Class id for AC or DC
            length -= 1
            byte = self.Get_bytes(1)
            class_id, table_id = (byte & 0xF0) >> 4, byte & 0x0F 
            print(f"Table ID = {table_id}, AC or DC = {class_id}, code = {byte}")
            
            # Bit lengths
            length -= 16
            bit_lengths = self.Get_bytes(16)
    
            # Symbols
            num_symbols = sum(bit_lengths)
            length -= num_symbols
            symbols = self.Get_bytes(num_symbols)
    
            # Build Huffman table
            huffman_table = Build_Huffman(bit_lengths, symbols)
            self.huffman_tables[(class_id, table_id)] = huffman_table

    def SOS_Process(self):
        # Read length
        length = self.Get_bytes(1) << 8 | self.Get_bytes(1)
        num_components = self.Get_bytes(1)
        print(f'SOS length = {length}, number of components = {num_components}')
        
        # Start decoding tables
        huffman_mappings = {'DC' : [], 'AC' : []}
        for i in range(3):
            [_, byte] = self.Get_bytes(2)
            huffman_mappings['DC'].append((byte & 0xF0) >> 4)
            huffman_mappings['AC'].append(byte & 0x0F)
    
        # Prepare MCU processing (Y : 0, Cb : 1, Cr : 2)
        mcu_width = 8 * self.image_info['components'][0]['h_factor']
        mcu_height = 8 * self.image_info['components'][0]['v_factor']
        mcus_per_row = (self.image_info['width'] + mcu_width - 1) // mcu_width
        mcus_per_col = (self.image_info['height'] + mcu_height - 1) // mcu_height
        #print(f'mcu_width = {mcu_width}, mcu_height = {mcu_height}')
        #print(f'mcu_row = {mcus_per_row}, mcu_col = {mcus_per_col}')
        YCbCr_data = {'Y': [], 'Cb': [], 'Cr': []}
        DC_prev = {'Y' : 0, 'Cb' : 0, 'Cr' : 0}
        for i in range(mcus_per_row):
            for j in range(mcus_per_col):
                for _ in range(4):
                    block, DC_prev['Y'] = self.MCU_Decode(huffman_mappings, DC_prev['Y'], 0)
                    YCbCr_data['Y'].append(block)
        
                # Cb Block
                YCbCr_data['Cb'], DC_prev['Cb'] = self.MCU_Decode(huffman_mappings, DC_prev['Cb'], 1)
        
                # Cr Block
                YCbCr_data['Cr'], DC_prev['Cr'] = self.MCU_Decode(huffman_mappings, DC_prev['Cr'], 2)
                #print(DC_prev)
        print(huffman_mappings)

    def MCU_Decode(self, huffman_mappings, DC_prev, type):
        coeffs = [0] * 64
        DC_table = self.huffman_tables[(0, huffman_mappings['DC'][type])] 
        AC_table = self.huffman_tables[(1, huffman_mappings['AC'][type])]
    
        # Decode DC coefficient
        code_len, num = self.Huffman_Decode(DC_table), 0
        
        for i in range(code_len):
            num = num * 2 + self.Get_bit()
            
        DC_diff = Bit_Length_Decode(code_len, num)
        coeffs[0] = DC_diff + DC_prev
        #print(coeffs[0])
        
        # Decode AC coefficients
        i = 1
        while i < 64:
            value = self.Huffman_Decode(AC_table)
            if value == 0 : break # End of Block
                
            i += value >> 4
            code_len, num = value & 0x0F, 0
            for j in range(code_len):
                num = num * 2 + self.Get_bit()
                
            if i < 64:
                coeffs[i] = Bit_Length_Decode(code_len, num)
                i += 1

        return coeffs, coeffs[0]

def Bit_Length_Decode(code_len, num):
    if code_len == 0 : return 0
    # Threshold for checking if num is positive
    threshold = (1 << (code_len - 1))
    
    if num < threshold : num -= 2 * threshold - 1 # Negative case
    return num 

def Build_Huffman(bit_lengths, symbols):
    code = 0
    symbol_index = 0
    huffman_table = {}
    for bit_length, num_codes in enumerate(bit_lengths, start = 1):
        for _ in range(num_codes):
            # Convert to binary string
            binary_code = f"{code:0{bit_length}b}" # I learned this trick from the internet
            huffman_table[binary_code] = symbols[symbol_index]
            symbol_index += 1
            code += 1
        code <<= 1

    return huffman_table

JPEG_Decoder = JPEG_Decoder('monalisa.jpg')
JPEG_Decoder.Parse()
#print(JPEG_Decoder.huffman_tables)
#print(JPEG_Decoder.image_info)
