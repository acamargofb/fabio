#!/usr/bin/env python
"""
Authors: Henning O. Sorensen & Erik Knudsen
         Center for Fundamental Research: Metal Structures in Four Dimensions
         Risoe National Laboratory
         Frederiksborgvej 399
         DK-4000 Roskilde
         email:erik.knudsen@risoe.dk

        + Jon Wright, ESRF
        + Jerome Kieffer, ESRF
"""

import numpy as np, logging

from fabio.fabioimage import fabioimage


BLOCKSIZE = 512
DATA_TYPES = {  "SignedByte"     :  np.int8,
                "UnsignedByte"   :  np.uint8,
                "SignedShort"    :  np.int16,
                "UnsignedShort"  :  np.uint16,
                "UnsignedShortInteger" : np.uint16,
                "SignedInteger"  :  np.int32,
                "UnsignedInteger":  np.uint32,
                "SignedLong"     :  np.int32,
                "UnsignedLong"   :  np.uint32,
                "FloatValue"     :  np.float32,
                "FLOATVALUE"     :  np.float32,
                "FLOAT"          :  np.float32, # fit2d
                "Float"          :  np.float32, # fit2d
                "DoubleValue"    :  np.float64
                }

MINIMUM_KEYS = ['HEADERID',
                'IMAGE',
                'BYTEORDER',
                'DATATYPE',
                'DIM_1',
                'DIM_2',
                'SIZE'] # Size is thought to be essential for writing at least

DEFAULT_VALUES = {"HeaderID":  "EH:000001:000000:000000",
                  "Image":   "1",
                  "ByteOrder":  "LowByteFirst", # FIXME?
                  "DataType": "FLOAT"
                  }

STATIC_HEADER_ELEMENTS = ("HeaderID", "Image", "ByteOrder", "DataType",
                        "Dim_1", "Dim_2", "Dim_3",
                        "Offset_1", "Offset_2", "Offset_3",
                        "Size")
STATIC_HEADER_ELEMENTS_CAPS = ("HEADERID", "IMAGE", "BYTEORDER", "DATATYPE",
                             "DIM_1", "DIM_2", "DIM_3",
                             "OFFSET_1", "OFFSET_2", "OFFSET_3",
                             "SIZE")


class edfimage(fabioimage):
    """ Read and try to write the ESRF edf data format """

    def __init__(self, data=None , header=None):
        fabioimage.__init__(self, data, header)
        #Dictionary containing the header-KEY -> header-Key as EDF keys are supposed to be key insensitive 
        self.frameCapsHeader = []
        self.framesHeaders = []
        self.framesData = []
        self.framesListHeader = []
        self.framesDims = []
        self.framesSize = []
        self.framesBpp = []


    def _readHeader(self, infile):
        """
        Read in a header in some EDF format from an already open file
        
        @param infile: file object open in read mode
        @return: string (or None if no header was found. 
        """

        block = infile.read(BLOCKSIZE)
        if len(block) < BLOCKSIZE:
            return
        if block[:4].find("{") < 0 :
            # This does not look like an edf file
            logging.warning("no opening {. Corrupt header of EDF file " + \
                            str(infile.name))
            return
        while '}' not in block:
            block = block + infile.read(BLOCKSIZE)
            if len(block) > BLOCKSIZE * 20:
                logging.warning("Runaway header in EDF file")
                return
        start = block.find("{") + 1
        end = block.find("}")

        # Now it is essential to go to the start of the binary part
        if end >= len(block) - 2:
            block = block + infile.read(BLOCKSIZE)
        if block[end, end + 3] == "}\r\n":
            offset = len(block) - end + 3
        elif block[end, end + 2] == "}\n":
            offset = len(block) - end + 2
        else:
            logging.error("Unable to locate start of the binary section")
            offset = None
        if offset is not None:
            infile.seek(-offset)

        return block[start:end]


    def _parseheader(self, block):
        """
        Parse the header in some EDF format from an already open file

        @param block: string representing the header block
        @type block: string, should be full ascii
        @return: size of the binary blob
        """
        header = {}
        dictCapsHeader = {}
        header_keys = []
        for line in block.split(';'):
            if '=' in line:
                key, val = line.split('=' , 1)
                header[key.strip()] = val.strip()
                dictCapsHeader[key.upper()] = key
                header_keys.append(key)
        missing = []
        for item in MINIMUM_KEYS:
            if item not in self.frameCapsHeader:
                missing.append(item)
        if len(missing) > 0:
            logging.warning("EDF file misses the keys: " + " ".join(missing))
        self.frameCapsHeader.append(dictCapsHeader)
        self.framesHeaders.append(header)
        self.framesListHeader.append(header_keys)

        # Compute image size
        size = None
        calcsize = 1
        if "SIZE" in dictCapsHeader:
            try:
                size = int(header[dictCapsHeader["SIZE"]])
            except ValueError:
                logging.warning("Unable to convert to integer : %s %s " % (dictCapsHeader["SIZE"], header[dictCapsHeader["SIZE"]]))
        if "DIM_1" in dictCapsHeader:
            try:
                dim1 = int(header[dictCapsHeader['DIM_1']])
            except ValueError:
                logging.error("Unable to convert to integer Dim_1: %s %s"(dictCapsHeader["DIM_1"], header[dictCapsHeader["DIM_1"]]))
            else:
                calcsize *= dim1
        else:
            logging.error("No Dim_1 in headers !!!")
        if "DIM_2" in dictCapsHeader:
            try:
                dim2 = int(header[dictCapsHeader['DIM_2']])
            except ValueError:
                logging.error("Unable to convert to integer Dim_3: %s %s"(dictCapsHeader["DIM_2"], header[dictCapsHeader["DIM_2"]]))
            else:
                calcsize *= dim2
        else:
            logging.error("No Dim_2 in headers !!!")
        if "DIM_3" in dictCapsHeader:
            try:
                dim3 = int(header[dictCapsHeader['DIM_3']])
            except ValueError:
                logging.error("Unable to convert to integer Dim_3: %s %s"(dictCapsHeader["DIM_3"], header[dictCapsHeader["DIM_3"]]))
                dim3 = None
            else:
                calcsize *= dim3
        else:
            logging.debug("No Dim_3 -> it is a 2D image")

        if "DATATYPE" in dictCapsHeader:
            bytecode = DATA_TYPES[header[dictCapsHeader['DATATYPE']]]
        else:
            bytecode = np.uint16
            logging.warning("Defaulting type to uint16")
        bpp = len(np.array(0, bytecode).tostring())
        calcsize *= bpp
        if (size is None):
            size = calcsize
        elif (size != calcsize):
            if ("COMPRESSION" in dictCapsHeader) and (header[dictCapsHeader['COMPRESSION']].upper().startwith("NO")):
                logging.error("Mismatch between the expected size %s and the calculated one %s" % (size, calcsize))
        if dim3 is None:
            self.framesSize.append((dim1, dim2))
        else:
            self.framesSize.append((dim1, dim2, dim3))
        self.framesBpp.append(bpp)
        self.framesSize.append(size)
        return size


    def read(self, fname):
        """
        Read in header into self.header and
            the data   into self.data
        """
        self.header = {}
        self.resetvals()
        infile = self._open(fname, "rb")
        bContinue = True
        while bContinue:
            block = self._readHeader(infile)
            if block is None:
                bContinue = False
                break
            size = self._parsefile(infile)
            datablock = infile.read(size)
            if len(datablock) != size:
                logging.warning("Non complete datablock: got %s, expected %s" % (len(datablock), size))
                bContinue = False
                break




        block = infile.read()
        expected_size = self.dim1 * self.dim2 * self.bpp

        if len(block) != expected_size:
            # The binary which has been read in does not match the size 
            # expected. Two cases are known:
            ####    1 extra byte (\0) at the end of the header (ImagePro)
            ####    Padding to 512 bytes, image is at the beginning 
            # These overlap in the case of an image of, eg:
            #       1024x1024-1 == 825x1271
            # To distinguish, we look for a header key:
            padded = False
            nbytesread = len(block)
            if self.header.has_key("EDF_BinarySize"):
                if int(self.header["EDF_BinarySize"]) == nbytesread:
                    padded = True
            if self.header.has_key("Size"):
                if int(self.header["Size"]) == nbytesread:
                    padded = True
            if padded:
                block = block[:expected_size]
                if self.header.has_key("EDF_BlockBoundary"):
                    chunksize = int(self.header["EDF_BlockBoundary"])
                else:
                    chunksize = 512
                if nbytesread % chunksize != 0:
                    # Unexpected padding
                    logging.warning("EDF file is strangely padded, size " +
                            str(nbytesread) + " is not multiple of " +
                            str(chunksize) + ", please verify your image")
            else: # perhaps not padded                
                # probably header overspill (\0)
                logging.warning("Read too many bytes, got " + str(len(block)) + \
                                " want " + str(expected_size))
                block = block[-expected_size:]
        if len(block) < expected_size:
            # FIXME
            logging.warning("Padded")
        infile.close()

        #now read the data into the array
        try:
            self.data = np.reshape(
                np.fromstring(block, bytecode),
                [self.dim2, self.dim1])
        except:
            print len(block), bytecode, self.bpp, self.dim2, self.dim1
            raise IOError, \
              'Size spec in edf-header does not match size of image data field'
        self.bytecode = self.data.dtype.type
        swap = self.swap_needed()
        if swap:
            self.data = self.data.byteswap()
            # Remove verbose arg - use logging and levels
            logging.info('Byteswapped from ' + self.header['ByteOrder'])
        else:
            logging.info('using ' + self.header['ByteOrder'])
        self.resetvals()
        # ensure the PIL image is reset
        self.pilimage = None
        return self


    def swap_needed(self):
        """
        Decide if we need to byteswap
        """
        if ('Low'  in self.header['ByteOrder'] and np.little_endian) or \
           ('High' in self.header['ByteOrder'] and not np.little_endian):
            return False
        if ('High'  in self.header['ByteOrder'] and np.little_endian) or \
           ('Low' in self.header['ByteOrder'] and not np.little_endian):
            if self.bpp in [2, 4, 8]:
                return True
            else:
                return False


    def _fixheader(self):
        """ put some rubbish in to allow writing"""
        self.header['Dim_2'], self.header['Dim_1'] = self.data.shape
        self.bpp = len(self.data[0, 0].tostring())
        self.header['Size'] = len(self.data.tostring())
        for k in MINIMUM_KEYS:
            if k not in self.header:
                self.header[k] = DEFAULT_VALUES[k]


    def getframe(self, num):
        """ returns the file numbered 'num' in the series as a fabioimage """
        if num in xrange(self.nframes):
            newImage = edfimage(data=self.framesData[num],
                                  header=self.framesHeaders[num])
            newImage.nframes = self.nframes
            newImage.currentframe = num
            newImage.fname = self.fname
            newImage.framesData = self.framesHeaders
            newImage.listHeader = self.framesHeaders
        else:
            logging.error("Cannot access frame: %s" % num)
            raise Exception("getframe out of range: %s" % num)


    def previous(self):
        """ returns the previous file in the series as a fabioimage """
        newFrameId = self.currentframe - 1
        return self.getframe(newFrameId)


    def next(self):
        """ returns the next file in the series as a fabioimage """
        newFrameId = self.currentframe + 1
        return self.getframe(newFrameId)


    def write(self, fname, force_type=None):
        """
        Try to write a file
        check we can write zipped also
        mimics that fabian was writing uint16 (we sometimes want floats)
        
        @param force_type: can be numpy.uint16 or simply "float"
        @return: None
        
        """
        self._fixheader()
        # Fabian was forcing uint16 - make this a default
        if force_type is not None:
            data = self.data.astype(force_type)
        else:
            data = self.data
        # Update header values to match the function local data object
        bpp = len(data[0, 0].tostring())
        if bpp not in [1, 2, 4]:
            logging.info("edfimage.write do you really want" + str(bpp) + \
                             "bytes per pixel??")
        bytecode = data.dtype.type
        for name , code in DATA_TYPES.items():
            if code == bytecode:
                self.header['DataType'] = name
                break
        dim2, dim1 = data.shape
        self.header['Dim_1'] = dim1
        self.header['Dim_2'] = dim2
        self.header['Size'] = dim1 * dim2 * bpp
        # checks for consistency:
        if bpp != self.bpp :
            logging.debug("Array upcasted? now " + str(bpp) + " was " + str(self.bpp))
        if dim1 != self.dim1 or dim2 != self.dim2 :
            logging.debug("corrupted image dimensions")
        outfile = self._open(fname, mode="wb")
        outfile.write('{\n') # Header start
        i = 4          # 2 so far, 2 to come at the end
        for k in self.header_keys:
            # We remove the extra whitespace on the key names to
            # avoiding making headers greater then 4 kb unless they already
            # were too big
            out = (("%-14s = %s ;\n") % (k, self.header[k]))
            i = i + len(out)
            outfile.write(out)
        # if additional items in the header just write them out in the
        # order they happen to be in
        for key, val in self.header.iteritems():
            if key in self.header_keys:
                continue
            out = (("%s = %s;\n") % (key, val))
            i = i + len(out)
            outfile.write(out)
        if i < 4096:
            out = (4096 - i) * ' '
        else:
            out = (1024 - i % 1024) * ' '  # Should make a total
            logging.warning("EDF Header is greater than 4096 bytes")
        outfile.write(out)
        i = i + len(out)
        assert i % 1024 == 0
        outfile.write('}\n')
        # print "Byteswapping?",
        if self.swap_needed():
            # print "did a swap"
            # data has "astype" from start of this function
            outfile.write(data.byteswap().tostring())
        else:
            # print "did not"
            outfile.write(data.tostring())
        outfile.close()