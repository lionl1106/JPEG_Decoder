def Read_JPEG(file_path):
    with open(file_path, 'rb') as file:
        data = file.read()
    return data

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

def SOF_Process(jpeg_data, start):
    start += 2
    # Read length
    length = jpeg_data[start] << 8 | jpeg_data[start + 1]
    print(f'SOF sequence length = {length}')
    
    image_info = {
        'precision': jpeg_data[start + 2],
        'height': jpeg_data[start + 3] << 8 | jpeg_data[start + 4],
        'width': jpeg_data[start + 5] << 8 | jpeg_data[start + 6],
        'num_components': jpeg_data[start + 7],
        'components': []
    }

    # Extract component information
    pos, end = start + 8, start + length
    while pos < end:
        component_id = jpeg_data[pos]
        sampling_factors = jpeg_data[pos + 1]
        h_sampling = sampling_factors >> 4
        v_sampling = sampling_factors & 0x0F
        quant_table_selector = jpeg_data[pos + 2]
        pos += 3
        image_info['components'].append({
            'id': component_id,
            'h_factor': h_sampling,
            'v_factor': v_sampling,
            'quant_table': quant_table_selector
        })

    return image_info, pos

def DQT_Process(jpeg_data, start, quantization_tables):
    start += 2
    # Read length
    length = jpeg_data[start] << 8 | jpeg_data[start + 1]
    print(f'DQT sequence length = {length}')
    
    # Start decoding tables
    pos, end = start + 2, start + length
    while pos < end:
        # Read Table Information
        precision = (jpeg_data[pos] & 0xF0) >> 4
        table_id  = jpeg_data[pos] & 0x0F
        pos += 1
        
        # Read Quantization Table
        if precision == 0:
            table_size = 64
            quantization_tables[table_id] = [i for i in jpeg_data[pos:pos + table_size]]
        elif precision == 1:
            table_size = 128
            quantization_tables[table_id] = [jpeg_data[pos + i] << 8 | jpeg_data[pos + i + 1] for i in range(0, table_size, 2)]
        else:
            raise ValueError("Unsupported precision")
        pos += table_size
    
    return quantization_tables, pos

def DHT_Process(jpeg_data, start, huffman_tables):
    start += 2
    # Read length
    length = jpeg_data[start] << 8 | jpeg_data[start + 1]
    print(f'DHT sequence length = {length}')
    
    # Start decoding tables
    pos, end = start + 2, start + length
    while pos < end:
        # Class id for AC or DC
        class_id = (jpeg_data[pos] & 0xF0) >> 4  
        table_id = jpeg_data[pos] & 0x0F  
        pos += 1

        # Bit lengths
        bit_lengths = jpeg_data[pos:pos + 16]
        pos += 16

        # Symbols
        num_symbols = sum(bit_lengths)
        symbols = jpeg_data[pos:pos + num_symbols]
        pos += num_symbols

        # Build Huffman table
        huffman_table = Build_Huffman(bit_lengths, symbols)
        huffman_tables[(class_id, table_id)] = huffman_table

    return huffman_tables, pos

def SOS_Process(jpeg_data, start):
    start += 2
    # Read length
    length = jpeg_data[start] << 8 | jpeg_data[start + 1]
    print(f'SOS components = {length}')
    end = start + length

    pos = start + 2
    print(jpeg_data[pos : end])
    
    return end
    
file_path = 'monalisa.jpg'
jpeg_data = Read_JPEG(file_path)

data_size = len(jpeg_data)-1
huffman_tables, quantization_tables = {}, {}
i, is_end = 0, 0
while(not is_end and i < data_size):
    code = jpeg_data[i] << 8 | jpeg_data[i+1]
    match code:
        case 0xFFD8:
            i += 1
            print(format(code, 'x'), 'Start of the image')
        case 0xFFDB:
            print(format(code, 'x'), 'Quantization tables')
            quantization_tables, i = DQT_Process(jpeg_data, i, quantization_tables)
        case 0xFFC4:
            print(format(code, 'x'), 'Huffman tables')
            huffman_tables, i = DHT_Process(jpeg_data, i, huffman_tables)
        case 0xFFC0:
            print(format(code, 'x'), 'Image structures')
            image_info, i = SOF_Process(jpeg_data, i)
        case 0xFFDA:
            print(format(code, 'x'), 'Start of decompressing')
            i = SOS_Process(jpeg_data, i)
        case 0xFFD9:
            i += 1
            print(format(code, 'x'), 'End of the image')
            is_end = 1
        case _:
            i += 1
            pass

#image_info
#print(quantization_tables)
#print(huffman_tables)
#print(jpeg_data)