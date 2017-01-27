# encoding: utf-8
# Copyright (c) 2017, Christian C. Sachs
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright
#   notice, this list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
# * Neither the name of the copyright holders nor the names of any
#   contributors may be used to endorse or promote products derived
#   from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import numpy as np

import warnings

with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    # code tend to throw warnings because of missing C extensions
    import imagej_tiff_meta.tifffile as patchy_tifffile

# https://github.com/imagej/imagej1/blob/2a6c191b027b5b1f5f22484506159f80adda21c5/ij/io/TiffDecoder.java

CONSTANT_MAGIC_NUMBER = 0x494a494a  # "IJIJ"
CONSTANT_INFO = 0x696e666f  # "info" (Info image property)
CONSTANT_LABELS = 0x6c61626c  # "labl" (slice labels)
CONSTANT_RANGES = 0x72616e67  # "rang" (display ranges)
CONSTANT_LUTS = 0x6c757473  # "luts" (channel LUTs)
CONSTANT_ROI = 0x726f6920  # "roi " (ROI)
CONSTANT_OVERLAY = 0x6f766572  # "over" (overlay)

CONST_IJ_POLYGON,\
    CONST_IJ_RECT,\
    CONST_IJ_OVAL,\
    CONST_IJ_LINE,\
    CONST_IJ_FREELINE,\
    CONST_IJ_POLYLINE,\
    CONST_IJ_NOROI,\
    CONST_IJ_FREEHAND,\
    CONST_IJ_TRACED,\
    CONST_IJ_ANGLE,\
    CONST_IJ_POINT\
    = range(11)


# https://github.com/imagej/imagej1/blob/86280b4e0756d1f4c0fcb44ac7410138e8e6a6d8/ij/io/RoiDecoder.java

IMAGEJ_ROI_HEADER = [
    ('_iout', '4a1'),  # always b'Iout'
    ('version', 'i2'),
    ('roi_type', 'i1'),
    ('_pad_byte', 'u1'),
    ('top', 'i2'),
    ('left', 'i2'),
    ('bottom', 'i2'),
    ('right', 'i2'),
    ('n_coordinates', 'i2'),
    ('x1', 'i4'),
    ('y1', 'i4'),
    ('x2', 'i4'),
    ('y2', 'i4'),
    ('stroke_width', 'i2'),
    ('shape_roi_size', 'i4'),
    ('stroke_color', 'i4'),
    ('fill_color', 'i4'),
    ('subtype', 'i2'),
    ('options', 'i2'),
    ('arrow_style_or_aspect_ratio', 'u1'),
    ('arrow_head_size', 'u1'),
    ('rounded_rect_arc_size', 'i2'),
    ('position', 'i4'),
    ('header2_offset', 'i4'),
]

IMAGEJ_ROI_HEADER2 = [
    ('_nil', 'i4'),
    ('c', 'i4'),
    ('z', 'i4'),
    ('t', 'i4'),
    ('name_offset', 'i4'),
    ('name_length', 'i4'),
    #
    ('overlay_label_color', 'i4'),
    ('overlay_font_size', 'i2'),
    ('available_byte1', 'i1'),
    ('image_opacity', 'i1'),
    ('image_size', 'i4'),
    ('float_stroke_width', 'f4'),
    ('roi_props_offset', 'i4'),
    ('roi_props_length', 'i4'),
    ('counters_offset', 'i4')
]

IMAGEJ_META_HEADER = [
    ('magic', 'i4'),
    ('type', 'i4'),
    ('count', 'i4'),
]

IJM_ROI_VERSION = 226


def new_record(dtype, data=None, offset=0):
    tmp = np.recarray(shape=(1,), dtype=dtype, aligned=False, buf=data, offset=offset).newbyteorder('>')[0]
    if data is None:
        tmp.fill(0)  # recarray does not initialize empty memory! that's pretty scary
    return tmp


IMAGEJ_SUPPORTED_OVERLAYS = {
        CONST_IJ_POLYGON,
        CONST_IJ_FREEHAND,
        CONST_IJ_TRACED,
        CONST_IJ_POLYLINE,
        CONST_IJ_FREELINE,
        CONST_IJ_ANGLE,
        CONST_IJ_POINT
    }


def imagej_parse_overlay(data):
    header = new_record(IMAGEJ_ROI_HEADER, data=data)

    header2 = new_record(IMAGEJ_ROI_HEADER2, data=data, offset=header.header2_offset)

    if header2.name_offset > 0:
        name = str(data[header2.name_offset:header2.name_offset + header2.name_length * 2], 'utf-16be')
    else:
        name = ''

    overlay = dict(name=name, coordinates=None)

    if header.roi_type in IMAGEJ_SUPPORTED_OVERLAYS:
        overlay['coordinates'] = np.ndarray(
            shape=(header.n_coordinates, 2),
            dtype=np.dtype(np.int16).newbyteorder('>'),
            buffer=data[header.itemsize:header.itemsize + 2 * 2 * header.n_coordinates],
            order='F'
        ).copy()

    for to_insert in [header, header2]:
        for key in to_insert.dtype.names:
            if key[0] == '_':
                continue
            overlay[key] = np.asscalar(getattr(to_insert, key))

    return overlay


def imagej_create_roi(points, name=None, c=0, z=0, t=0, index=None):
    if name is None:
        if index is None:
            name = 'F%02d-%x' % (t+1, np.random.randint(0, 2**32 - 1),)
        else:
            name = 'F%02d-C%d' % (t+1, index,)

    points = points.copy()
    left, top = points[:, 0].min(), points[:, 1].min()
    points[:, 0] -= left
    points[:, 1] -= top

    encoded_data = points.astype(np.dtype(np.int16).newbyteorder('>')).tobytes(order='F')

    encoded_data_size = len(encoded_data)

    header = new_record(IMAGEJ_ROI_HEADER)

    header._iout = b'I', b'o', b'u', b't'

    header.version = IJM_ROI_VERSION

    header.roi_type = CONST_IJ_FREEHAND  # CONST_IJ_POLYGON

    header.left = left
    header.top = top

    header.n_coordinates = len(points)

    header.options = 40
    header.position = t + 1
    header.header2_offset = header.itemsize + encoded_data_size

    header2 = new_record(IMAGEJ_ROI_HEADER2)

    # header.position is enough, otherwise it will not work as intended

    # header2.c = c + 1
    # header2.z = z + 1
    # header2.t = t + 1

    header2.name_offset = header.header2_offset + header2.itemsize
    header2.name_length = len(name)

    return header.tobytes() + encoded_data + header2.tobytes() + name.encode('utf-16be')


def imagej_prepare_metadata(overlays):
    mh = new_record(IMAGEJ_META_HEADER)

    mh.magic = CONSTANT_MAGIC_NUMBER

    # mh.type = CONSTANT_ROI
    mh.type = CONSTANT_OVERLAY
    mh.count = len(overlays)

    meta_data = mh.tobytes() + b''.join(overlays)

    byte_counts = [mh.itemsize] + [len(r) for r in overlays]  # len of overlays

    return meta_data, byte_counts

###
# Monkey patching
###


def TiffWriter___init__(self, filename):
    self.__original_init__(
        filename,
        bigtiff=False,
        imagej=True,
        byteorder='>'
    )

    self._ijm_roi_data = []
    self._ijm_rois_per_frame = {}
    self._ijm_first_written = False


def TiffWriter_add_roi(self, points, name=None, c=0, z=0, t=0):
    index = None
    if name is None:
        if t not in self._ijm_rois_per_frame:
            self._ijm_rois_per_frame[t] = 0
        self._ijm_rois_per_frame[t] += 1
        index = self._ijm_rois_per_frame[t]

    self._ijm_roi_data.append(imagej_create_roi(points, name=name, c=c, z=z, t=t, index=index))


def TiffWriter_new_save(self, data, **kwargs):
    if self._ijm_first_written or len(self._ijm_roi_data) == 0:
        return self.__original_save(data)

    meta_data, byte_counts = imagej_prepare_metadata(self._ijm_roi_data)

    self._ijm_first_written = True

    return self.__original_save(
        data,
        extratags=[
            (50838, 'I', len(byte_counts), byte_counts, True),  # byte counts
            (50839, 'B', len(meta_data), np.frombuffer(meta_data, dtype=np.uint8), True),  # meta data
            # (34122, 'I', 1, [self._ijm_frames], True)  # meta data
            ]
    )


def new_imagej_metadata(*args):
    result = __original_imagej_metadata(*args)

    if 'overlays' in result:
        result['parsed_overlays'] = [
            patchy_tifffile.Record(imagej_parse_overlay(data))
            for data in result['overlays']
        ]

    return result


# monkey patching

patchy_tifffile.TiffWriter.__original_init__ = patchy_tifffile.TiffWriter.__init__
patchy_tifffile.TiffWriter.__init__ = TiffWriter___init__
patchy_tifffile.TiffWriter.__original_save = patchy_tifffile.TiffWriter.save
patchy_tifffile.TiffWriter.save = TiffWriter_new_save
patchy_tifffile.TiffWriter.add_roi = TiffWriter_add_roi

TiffWriter = patchy_tifffile.TiffWriter

__original_imagej_metadata = patchy_tifffile.imagej_metadata

patchy_tifffile.imagej_metadata = new_imagej_metadata

TiffFile = patchy_tifffile.TiffFile