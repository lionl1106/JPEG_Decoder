def read_jpeg(file_path):
    with open(file_path, 'rb') as file:
        data = file.read()
    return data

def DQT_Process(jpeg_data, start):
    
    # Read length
    length = jpeg_data[start + 2] << 8 | jpeg_data[start + 3]
    print(f'length = {length}')
    end = start + length
    
    # Start decoding tables
    pos = start + 4
    quantization_tables = {}
    while pos < end:
        # Read Table Information
        precision = jpeg_data[pos] & 0xF0  # 0 for 8-bit, 1 for 16-bit
        table_id  = jpeg_data[pos] & 0x0F
        pos += 1
        
        # Read Quantization Table
        if precision == 0:
            table_size = 64  # 8-bit precision
            quantization_tables[table_id] = [i for i in jpeg_data[pos:pos + table_size]]
        elif precision == 1:
            table_size = 128  # 16-bit precision
            quantization_tables[table_id] = [jpeg_data[pos + i] << 8 | jpeg_data[pos + i + 1] for i in range(0, table_size, 2)]
        else:
            raise ValueError("Unsupported precision")
        pos += table_size
    
    return quantization_tables, pos

file_path = 'me.jpg'
jpeg_data = read_jpeg(file_path)

data_size = len(jpeg_data)-1
processing_queue = []
i, is_end = 0, 0
while(not is_end and i < data_size):
    code = jpeg_data[i] << 8 | jpeg_data[i+1]
    match code:
        case 0xFFD8:
            i += 1
            print(format(code, 'x'), 'Start of the image')
        case 0xFFDB:
            print(format(code, 'x'), 'Quantization tables')
            quantization_tables, i = DQT_Process(jpeg_data, i)
        case 0xFFC4:
            i += 1
            print(format(code, 'x'), 'Huffman tables')
        case 0xFFC0:
            i += 1
            print(format(code, 'x'), 'Image structures')
        case 0xFFDA:
            i += 1
            print(format(code, 'x'), 'Start of decompressing')
        case 0xFFD9:
            i += 1
            print(format(code, 'x'), 'End of the image')
            is_end = 1
        case _:
            i += 1
            pass

print(quantization_tables)
