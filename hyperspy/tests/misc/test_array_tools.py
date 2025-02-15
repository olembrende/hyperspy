# -*- coding: utf-8 -*-
# Copyright 2007-2022 The HyperSpy developers
#
# This file is part of HyperSpy.
#
# HyperSpy is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# HyperSpy is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with HyperSpy. If not, see <https://www.gnu.org/licenses/#GPL>.


import dask.array as da
import numpy as np
import pytest

from hyperspy.misc.array_tools import (
    dict2sarray,
    get_array_memory_size_in_GiB,
    get_signal_chunk_slice,
    numba_histogram,
    round_half_towards_zero,
    round_half_away_from_zero,
)

dt = [("x", np.uint8), ("y", np.uint16), ("text", (bytes, 6))]


@pytest.mark.parametrize(
    "dtype, size",
    [
        ("int32", 4.470348e-7),
        ("float64", 8.940697e-7),
        ("uint8", 1.117587e-7),
        (np.dtype(np.int16), 2.235174e-7),
    ],
)
def test_get_memory_size(dtype, size):
    mem = get_array_memory_size_in_GiB((2, 3, 4, 5), dtype=dtype)
    print(mem)
    np.testing.assert_allclose(mem, size)


def test_d2s_fail():
    d = dict(x=5, y=10, text='abcdef')
    with pytest.raises(ValueError):
        dict2sarray(d)


def test_d2s_dtype():
    d = dict(x=5, y=10, text='abcdef')
    ref = np.zeros((1,), dtype=dt)
    ref['x'] = 5
    ref['y'] = 10
    ref['text'] = 'abcdef'

    assert ref == dict2sarray(d, dtype=dt)


def test_d2s_extra_dict_ok():
    d = dict(x=5, y=10, text='abcdef', other=55)
    ref = np.zeros((1,), dtype=dt)
    ref['x'] = 5
    ref['y'] = 10
    ref['text'] = 'abcdef'

    assert ref == dict2sarray(d, dtype=dt)


def test_d2s_sarray():
    d = dict(x=5, y=10, text='abcdef')

    base = np.zeros((1,), dtype=dt)
    base['x'] = 65
    base['text'] = 'gg'

    ref = np.zeros((1,), dtype=dt)
    ref['x'] = 5
    ref['y'] = 10
    ref['text'] = 'abcdef'

    assert ref == dict2sarray(d, sarray=base)


def test_d2s_partial_sarray():
    d = dict(text='abcdef')

    base = np.zeros((1,), dtype=dt)
    base['x'] = 65
    base['text'] = 'gg'

    ref = np.zeros((1,), dtype=dt)
    ref['x'] = 65
    ref['y'] = 0
    ref['text'] = 'abcdef'

    assert ref == dict2sarray(d, sarray=base)


def test_d2s_type_cast_ok():
    d = dict(x='34', text=55)

    ref = np.zeros((1,), dtype=dt)
    ref['x'] = 34
    ref['y'] = 0
    ref['text'] = '55'

    assert ref == dict2sarray(d, dtype=dt)


def test_d2s_type_cast_invalid():
    d = dict(x='Test')
    with pytest.raises(ValueError):
        dict2sarray(d, dtype=dt)


def test_d2s_string_cut():
    d = dict(text='Testerstring')
    sa = dict2sarray(d, dtype=dt)
    assert sa['text'][0] == b'Tester'


def test_d2s_array1():
    dt2 = dt + [('z', (np.uint8, 4)), ('u', (np.uint16, 4))]
    d = dict(z=2, u=[1, 2, 3, 4])
    sa = dict2sarray(d, dtype=dt2)
    np.testing.assert_array_equal(sa['z'][0], [2, 2, 2, 2])
    np.testing.assert_array_equal(sa['u'][0], [1, 2, 3, 4])


def test_d2s_array2():
    d = dict(x=2, y=[1, 2, 3, 4])
    sa = np.zeros((4,), dtype=dt)
    sa = dict2sarray(d, sarray=sa)
    np.testing.assert_array_equal(sa['x'], [2, 2, 2, 2])
    np.testing.assert_array_equal(sa['y'], [1, 2, 3, 4])


def test_d2s_arrayX():
    dt2 = dt + [('z', (np.uint8, 4)), ('u', (np.uint16, 4))]
    d = dict(z=2, u=[1, 2, 3, 4])
    sa = np.zeros((4,), dtype=dt2)
    sa = dict2sarray(d, sarray=sa)
    np.testing.assert_array_equal(sa['z'], [[2, 2, 2, 2], ] * 4)
    np.testing.assert_array_equal(sa['u'], [[1, 2, 3, 4], ] * 4)


@pytest.mark.parametrize(
    'sig_chunks, index, expected',
    [((5, 5), (1, 1), [slice(0, 5, None), slice(0, 5, None)]),
     ((5, 5), (7, 7), [slice(5, 10, None), slice(5, 10, None)]),
     ((5, 5), (1, 12), [slice(0, 5, None), slice(10, 15, None)]),
     ((5, ), (1, ), [slice(0, 5, None), ]),
     ((20, ), (1, ), [slice(0, 20, None), ]),
     ((5, ), [1], [slice(0, 5, None), ]),
     ((5, ), (25, ), 'error'),
     ((20, 20), (25, 21), 'error'),
      ]
)
def test_get_signal_chunk_slice(sig_chunks, index, expected):
    ndim = 1 + len(index)
    data = da.zeros([20]*ndim, chunks=(10, *sig_chunks[::-1]))
    if expected == 'error':
        with pytest.raises(ValueError):
            chunk_slice = get_signal_chunk_slice(index, data.chunks)
    else:
        chunk_slice = get_signal_chunk_slice(index, data.chunks)
        assert chunk_slice == expected


@pytest.mark.parametrize(
    'sig_chunks, index, expected',
    [((5, 5), (12, 7), [slice(10, 15, None), slice(5, 10, None)]),
     ((5, 5), (7, 12), 'error'),
     ]
)
def test_get_signal_chunk_slice_not_square(sig_chunks, index, expected):
    data = da.zeros((2, 2, 10, 20), chunks=(2, 2, *sig_chunks[::-1]))
    if expected == 'error':
        with pytest.raises(ValueError):
            chunk_slice = get_signal_chunk_slice(index, data.chunks)
    else:
        chunk_slice = get_signal_chunk_slice(index, data.chunks)
        assert chunk_slice == expected


@pytest.mark.parametrize('dtype', ['<u2', 'u2', '>u2', '<f4', 'f4', '>f4'])
def test_numba_histogram(dtype):
    arr = np.arange(100, dtype=dtype)
    np.testing.assert_array_equal(numba_histogram(arr, 5, (0, 100)), [20, 20, 20, 20, 20])


def test_round_half_towards_zero_integer():
    a = np.array([-2.0, -1.7, -1.5, -0.2, 0.0, 0.2, 1.5, 1.7, 2.0])
    np.testing.assert_allclose(
        round_half_towards_zero(a, decimals=0),
        np.array([-2.0, -2.0, -1.0, 0.0, 0.0, 0.0, 1.0, 2.0, 2.0])
        )
    np.testing.assert_allclose(
        round_half_towards_zero(a, decimals=0),
        round_half_towards_zero(a)
        )


def test_round_half_towards_zero():
    a = np.array([-2.01, -1.56, -1.55, -1.50, -0.22, 0.0, 0.22, 1.50, 1.55, 1.56, 2.01])
    np.testing.assert_allclose(
        round_half_towards_zero(a, decimals=1),
        np.array([-2.0, -1.6, -1.5, -1.5, -0.2, 0.0, 0.2, 1.5, 1.5, 1.6, 2.0])
        )


def test_round_half_away_from_zero_integer():
    a = np.array([-2.0, -1.7, -1.5, -0.2, 0.0, 0.2, 1.5, 1.7, 2.0])
    np.testing.assert_allclose(
        round_half_away_from_zero(a, decimals=0),
        np.array([-2.0, -2.0, -2.0, 0.0, 0.0, 0.0, 2.0, 2.0, 2.0])
        )
    np.testing.assert_allclose(
        round_half_away_from_zero(a, decimals=0),
        round_half_away_from_zero(a)
        )


def test_round_half_away_from_zero():
    a = np.array([-2.01, -1.56, -1.55, -1.50, -0.22, 0.0, 0.22, 1.50, 1.55, 1.56, 2.01])
    np.testing.assert_allclose(
        round_half_away_from_zero(a, decimals=1),
        np.array([-2.0, -1.6, -1.6, -1.5, -0.2, 0.0, 0.2, 1.5, 1.6, 1.6, 2.0])
        )
