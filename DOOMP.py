# MIT License
#
# Copyright (c) 2022 Christopher Holzmann Pérez
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.



from binary_reader import BinaryReader, Endian
import argparse
import sys
import os



class PackedFile:
    def __init__(self):
        self.filename = ""
        self.extension = ""
        self.start_offset = 0
        self.size = 0
        self.data = bytearray()
    
    def dat_to_file(self, reader, path):
        print(f"Unpacking {self.filename} ({self.size} bytes)")
        reader.seek(self.start_offset)
        self.data = reader.read_bytes(self.size)
        with open(path + self.filename, 'wb') as unpacked_file:
            unpacked_file.write(self.data)
            unpacked_file.close()

    def set_extension_from_filename(self):
        self.extension = self.filename.split(".")[-1]

    def file_to_dat(self, writer, path):
        print(f"Packing {self.filename} ({self.size} bytes)")
        writer.align(0x10)
        self.start_offset = writer.pos()
        file_path = path + "/" + self.filename
        file = open(file_path, "rb")
        file_bytearray = bytearray(file.read())
        writer.write_bytes(bytes(file_bytearray))
        writer.align(0x10)



def unpackDAT(path, is_console=False):
    with open(path, "rb") as f:
        reader = BinaryReader(f.read())
        if reader.read_str(4) != 'DAT':
            raise Exception('Incorrect magic. Expected DAT')

        if is_console: reader.set_endian(Endian.BIG)

        file_number = reader.read_int32() #0x4
        ptr_file_data_offset_table = reader.read_uint32() #0x8
        ptr_file_extension_table = reader.read_uint32() #0xC
        ptr_filename_table = reader.read_uint32() #0x10
        ptr_file_size_table = reader.read_uint32() #0x14
        ptr_unknown = reader.read_uint32() #0x18

        print(f"Found {file_number} files.")

        #List init
        packed_file_list = []
        for i in range(file_number):
            packed_file_list.append(PackedFile())

        #File data offsets
        reader.seek(ptr_file_data_offset_table)
        for i in range(file_number):
            data_offset = reader.read_uint32()
            packed_file_list[i].start_offset = data_offset
        
        #File extensions
        reader.seek(ptr_file_extension_table)
        for i in range(file_number):
            ext = reader.read_str(4)
            packed_file_list[i].extension = ext
        
        #Filenames
        reader.seek(ptr_filename_table)
        filename_size = reader.read_int32() #Fixed string size
        for i in range(file_number):
            name = reader.read_str(filename_size)
            packed_file_list[i].filename = name
        
        #File size
        reader.seek(ptr_file_size_table)
        for i in range(file_number):
            size = reader.read_uint32()
            packed_file_list[i].size = size

        #Unpack files
        out_path = path + ".unpack/"
        if not os.path.exists(out_path):
            os.makedirs(out_path)
        for i in range(file_number):
            packed_file_list[i].dat_to_file(reader, out_path)
    
    f.close()



def repackDAT(path, is_console=False):
    dir_list = os.listdir(path)
    filename_list = []
    for name in dir_list:
        if os.path.isfile(path + "/" + name):
            filename_list.append(name)
    file_number = len(filename_list)
    print(f"Found {file_number} files.")

    writer = BinaryReader()
    if is_console: writer.set_endian(Endian.BIG)
    writer.write_str_fixed('DAT', 0x4) #Magic
    writer.write_uint32(file_number) #Amount of files. 0x4
    writer.write_uint32(0x20) #Pointer to data offset table. 0x8
    writer.write_uint32(0) #Placeholder pointer to file extension table. 0xC
    writer.write_uint32(0) #Placeholder pointer to filename table. 0x10
    writer.write_uint32(0) #Placeholder pointer to file size table. 0x14
    writer.write_uint32(0) #Placeholder pointer to unknown data table. 0x18
    writer.write_uint32(0) #Padding

    #List init, set filenames, extensions and sizes
    packed_file_list = []
    max_namefile_size = 0
    for i in range(file_number):
        pf = PackedFile()
        pf.filename = filename_list[i]
        if len(pf.filename) > max_namefile_size: max_namefile_size = len(pf.filename) + 1
        pf.set_extension_from_filename()
        pf.size = os.path.getsize(path + "/" + pf.filename)
        packed_file_list.append(pf)
    
    #Placeholder pointers for the data offset table
    for i in range(file_number):
        writer.write_uint32(0) #Placeholder
    
    #File extension table
    et_ptr = writer.pos()
    for i in range(file_number):
        writer.write_str_fixed(packed_file_list[i].extension, 0x4)
    curr_pos = writer.pos()
    writer.seek(0xC)
    writer.write_int32(et_ptr)
    writer.seek(curr_pos)

    #Filename table
    nt_ptr = writer.pos()
    writer.write_uint32(max_namefile_size)
    for i in range(file_number):
        writer.write_str_fixed(packed_file_list[i].filename, max_namefile_size)
    curr_pos = writer.pos()
    writer.seek(0x10)
    writer.write_int32(nt_ptr)
    writer.seek(curr_pos)

    #File size table
    st_ptr = writer.pos()
    for i in range(file_number):
        writer.write_uint32(packed_file_list[i].size)
    curr_pos = writer.pos()
    writer.seek(0x14)
    writer.write_int32(st_ptr)
    writer.seek(curr_pos)

    #Write file data
    for i in range(file_number):
        packed_file_list[i].file_to_dat(writer, path)

    #Update data offset table
    writer.seek(0x20)
    for i in range(file_number):
        writer.write_uint32(packed_file_list[i].start_offset)

    #Save DAT
    new_path = rchop(path, ".unpack")
    with open(new_path, 'wb') as file:
        file.write(writer.buffer())
        file.close()



def rchop(s, suffix):
    if suffix and s.endswith(suffix):
        return s[:-len(suffix)]
    return s + ".dat"



if __name__ == '__main__':
    print(r'''
"But first you need to take a
______ _____  ________  _________ 
|  _  \  _  ||  _  |  \/  || ___ \
| | | | | | || | | | .  . || |_/ /
| | | | | | || | | | |\/| ||  __/ 
| |/ /\ \_/ /\ \_/ / |  | || |    
|___/  \___/  \___/\_|  |_/\_|    " -Doktor
                       
    ''')
    print("METAL GEAR RISING: REVENGEANCE DAT ARCHIVE (UN)PACKER \n")
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Input file (DAT) or directory", type=str)
    parser.add_argument("-c", "--console", help="Use if the file(s) originate from the console (PS3/Xbox 360) versions", required=False, action="store_true")
    args = parser.parse_args()

    path = args.input
    if path is None:
        parser.print_help()
        sys.exit(1)

    if os.path.isfile(path):
        unpackDAT(path, args.console)
    if os.path.isdir(path):
        repackDAT(path, args.console)