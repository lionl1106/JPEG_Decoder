def Marker_Parse(code):
    match code:
        case 0xFFD8:
            print(format(code, 'x'), 'Start of the image')
        case 0xFFD9:
            print(format(code, 'x'), 'End of the image')
        case 0xFFDB:
            print(format(code, 'x'), 'Quantization tables')
        case 0xFFC4:
            print(format(code, 'x'), 'Huffman tables')
        case 0xFFC0:
            print(format(code, 'x'), 'Image structures')
        case 0xFFDA:
            print(format(code, 'x'), 'Start of decompressing')
        case _:
            pass

def read_jpeg(file_path):
    with open(file_path, 'rb') as file:
        data = file.read()
    return data

file_path = 'me.jpg'
jpeg_data = read_jpeg(file_path)

for i in range(len(jpeg_data)-4):
    Marker_Parse(jpeg_data[i] * 0x100 + jpeg_data[i+1])
        
print(jpeg_data[:])
