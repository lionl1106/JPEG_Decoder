import math
import time
from PIL import Image

class JPEG_Decoder:
    def __init__(self, filename):
        self.filename = filename
        self.image_info = {}
        self.quantization_tables, self.huffman_tables = {}, {}
        with open(filename, 'rb') as file:
            self.data = list(map(int, file.read()))

        self.pos, self.end = 0, len(self.data)
        self.bit_pos = -1
        DCT = [[0 for _ in range(8)] for _ in range(8)]
        for i in range(8):
            for j in range(8):
                DCT[i][j] = 1 / math.sqrt(8) * math.cos(math.pi * i * (0.5 + j) / 8)
                if i != 0:
                    DCT[i][j] *= math.sqrt(2)

        # Compute the Kronecker product of the DCT transpose matrix
        DCT_T = [[DCT[j][i] for j in range(8)] for i in range(8)]
        self.kron_matrix = self.Kronecker_Product(DCT_T, DCT_T)

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
            
        return huffman_table[code]

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
        self.image = [[[0 for channel in range(3)] for _ in range(self.image_info['width'])] for _ in range(self.image_info['height'])]

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
            #print(f"Table ID = {table_id}, AC or DC = {class_id}, code = {byte}")
            
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

        # Dont't need them
        _ = self.Get_bytes(3)
        print(_)
        # Prepare MCU processing (Y : 0, Cb : 1, Cr : 2)
        h_factor = self.image_info['components'][0]['h_factor']
        v_factor = self.image_info['components'][0]['v_factor']
        mcu_width = 8 * h_factor
        mcu_height = 8 * v_factor
        mcus_per_row = (self.image_info['width'] + mcu_width - 1) // mcu_width
        mcus_per_col = (self.image_info['height'] + mcu_height - 1) // mcu_height
        print(f'mcu_width = {mcu_width}, mcu_height = {mcu_height}')
        print(f'mcu_row = {mcus_per_row}, mcu_col = {mcus_per_col}')
        
        DC_prev = {'Y' : 0, 'Cb' : 0, 'Cr' : 0}
        for i in range(mcus_per_col):
            for j in range(mcus_per_row):
                #print(f'cnt = {cnt}', end = ' ')
                YCbCr_data = {'Y': [], 'Cb': [], 'Cr': []}
                for _ in range(v_factor * h_factor):
                    block, DC_prev['Y'] = self.MCU_Decode(huffman_mappings, DC_prev['Y'], 0)
                    YCbCr_data['Y'].append(block)
        
                # Cb Block
                block, DC_prev['Cb'] = self.MCU_Decode(huffman_mappings, DC_prev['Cb'], 1)
                YCbCr_data['Cb'].append(block)
                
                # Cr Block
                block, DC_prev['Cr'] = self.MCU_Decode(huffman_mappings, DC_prev['Cr'], 2)
                YCbCr_data['Cr'].append(block)

                for k in range(v_factor):
                    for l in range(h_factor):
                        for block_y in range(8):
                            y = i * mcu_height + 8 * k + block_y
                            if y >= self.image_info['height']: 
                                break
                            for block_x in range(8):
                                x = j * mcu_width + 8 * l + block_x
                                if x >= self.image_info['width']: 
                                    break
                                # +128 for the offset
                                self.image[y][x][0] = YCbCr_data['Y'][k * v_factor + l][block_y * 8 + block_x] #+ 128
                                self.image[y][x][1] = YCbCr_data['Cb'][0][block_y * 8 + block_x] #+ 128
                                self.image[y][x][2] = YCbCr_data['Cr'][0][block_y * 8 + block_x] #+ 128
                                
                
                #print(DC_prev)
        self.YCbCr_2_RGB()
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
        DC_prev = coeffs[0]
        
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
        
        coeffs = self.Dequantization(coeffs, self.quantization_tables[type > 0])
        coeffs = self.Inverse_Zigzag(coeffs)
        coeffs = self.IDCT(coeffs)
        #print(coeffs[0])
        
        return coeffs, DC_prev

    def Inverse_Zigzag(self, coeffs):
        zigzag_pattern = [0,  1,  5,  6,  14, 15, 27, 28,
                          2,  4,  7,  13, 16, 26, 29, 42,
                          3,  8,  12, 17, 25, 30, 41, 43,
                          9,  11, 18, 24, 31, 40, 44, 53,
                          10, 19, 23, 32, 39, 45, 52, 54,
                          20, 22, 33, 38, 46, 51, 55, 60,
                          21, 34, 37, 47, 50, 56, 59, 61,
                          35, 36, 48, 49, 57, 58, 62, 63]

        return [coeffs[zigzag_pattern[i]] for i in range(64)]

    def Dequantization(self, coeffs, Q_table):
        return [coeffs[i] * Q_table[i] for i in range(64)]

    def IDCT(self, coeffs):
        result = []
        for i in range(64):
            sum = 0
            for j in range(64):
                sum += self.kron_matrix[i][j] * coeffs[j]
            result.append(sum)
        return result

    def Kronecker_Product(self, m1, m2):
        # Create an empty result matrix with the proper dimensions
        m1_rows, m1_cols = len(m1), len(m1[0])
        m2_rows, m2_cols = len(m2), len(m2[0])
        
        # Fill in the result matrix
        result = [[0] * (m1_cols * m2_cols) for _ in range(m1_rows * m2_rows)]
        for i in range(m1_rows):
            for j in range(m1_cols):
                for k in range(m2_rows):
                    for l in range(m2_cols):
                        result[i * m2_rows + k][j * m2_cols + l] = m1[i][j] * m2[k][l]
        
        return result

    def YCbCr_2_RGB(self):

        height, width = len(self.image), len(self.image[0])
        for y in range(height):
            for x in range(width):
                Y, Cb, Cr = self.image[y][x][0], self.image[y][x][1], self.image[y][x][2]
                R = Y + 1.402 * Cr + 128
                G = Y - 0.344136 * Cb - 0.714136 * Cr + 128
                B = Y + 1.772 * Cb + 128
                self.image[y][x][0], self.image[y][x][1], self.image[y][x][2] = R, G, B

    def Make_BMP(self):
        # Create a new image
        im = Image.new('RGB', (self.image_info['width'], self.image_info['height']))
        
        # Put data into the image
        for y in range(self.image_info['height']):
            for x in range(self.image_info['width']):
                im.putpixel((x, y), tuple(map(int, self.image[y][x])))
                
        # Save the image
        im.save(f'{self.filename}.bmp')
        im.show()


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

filenames = ['monalisa', 'teatime', 'gig-sn08', 'gig-sn01']
for filename in filenames:
    start = time.time()
    jpeg_decoder = JPEG_Decoder(f'{filename}.jpg')
    jpeg_decoder.Parse()
    print(f'Time taken : {(time.time() - start) / 10000 * 10000}')
    jpeg_decoder.Make_BMP()
    