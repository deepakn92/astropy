# Licensed under a 3-clause BSD style license - see LICENSE.rst

"""
This module contains the classes and utility functions for distance and
cartesian coordinates.
"""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import numpy as np

from ..extern import six
from .. import units as u

__all__ = ['Distance', 'CartesianPoints', 'cartesian_to_spherical',
           'spherical_to_cartesian']


__doctest_requires__ = {'*': ['scipy.integrate']}


class Distance(u.Quantity):
    """
    A one-dimensional distance.

    This can be initialized in one of four ways:

    * A distance `value` (array or float) and a `unit`
    * A `~astropy.units.quantity.Quantity` object
    * A redshift and (optionally) a cosmology.
    * Providing a distance modulus

    Parameters
    ----------
    value : scalar or `~astropy.units.quantity.Quantity`
        The value of this distance
    unit : `~astropy.units.core.UnitBase`
        The units for this distance, *if* `value` is not a `Quantity`.
        Must have dimensions of distance.
    z : float
        A redshift for this distance.  It will be converted to a distance
        by computing the luminosity distance for this redshift given the
        cosmology specified by `cosmology`. Must be given as a keyword argument.
    cosmology : `~astropy.cosmology.Cosmology` or None
        A cosmology that will be used to compute the distance from `z`.
        If None, the current cosmology will be used (see
        `astropy.cosmology` for details).
    distmod : float or `~astropy.units.Quantity`
        The distance modulus for this distance.
    dtype : ~numpy.dtype, optional
        See `~astropy.units.Quantity`. Must be given as a keyword argument.
    copy : bool, optional
        See `~astropy.units.Quantity`. Must be given as a keyword argument.

    Raises
    ------
    astropy.units.core.UnitsError
        If the `unit` is not a distance.
    ValueError
        If `z` is provided with a `unit` or `cosmology` is provided when `z` is
        *not* given, or `value` is given as well as `z`

    Examples
    --------
    >>> from astropy import units as u
    >>> from astropy import cosmology
    >>> from astropy.cosmology import WMAP5, WMAP7
    >>> cosmology.set_current(WMAP7)
    >>> d1 = Distance(10, u.Mpc)
    >>> d2 = Distance(40, unit=u.au)
    >>> d3 = Distance(value=5, unit=u.kpc)
    >>> d4 = Distance(z=0.23)
    >>> d5 = Distance(z=0.23, cosmology=WMAP5)
    >>> d6 = Distance(distmod=24.47)
    """

    def __new__(cls, value=None, unit=None, z=None, cosmology=None,
                distmod=None, dtype=None, copy=True):
        from ..cosmology import get_current

        if isinstance(value, u.Quantity):
            # This includes Distances as well
            if z is not None or distmod is not None:
                raise ValueError('`value` was given along with `z` or `distmod`'
                                 ' in Quantity constructor.')

            if unit is not None:
                value = value.to(unit).value
            else:
                unit = value.unit
                value = value.value
        elif value is None:
            if z is not None:
                if distmod is not None:
                    raise ValueError('both `z` and `distmod` given in Distance '
                                     'constructor')

                if cosmology is None:
                    cosmology = get_current()

                ld = cosmology.luminosity_distance(z)

                if unit is not None:
                    ld = ld.to(unit)
                value = ld.value
                unit = ld.unit

            elif distmod is not None:
                value = cls._distmod_to_pc(distmod)
                if unit is None:
                    # choose unit based on most reasonable of Mpc, kpc, or pc
                    if value > 1e6:
                        value = value / 1e6
                        unit = u.megaparsec
                    elif value > 1e3:
                        value = value / 1e3
                        unit = u.kiloparsec
                    else:
                        unit = u.parsec
                else:
                    value = u.Quantity(value, u.parsec).to(unit).value
            else:
                raise ValueError('none of `value`, `z`, or `distmod` were given'
                                 ' to Distance constructor')

                value = ld.value
                unit = ld.unit
        elif z is not None:  # and value is not None based on above
            raise ValueError('Both `z` and a `value` were provided in Distance '
                             'constructor')
        elif cosmology is not None:
            raise ValueError('A `cosmology` was given but `z` was not provided '
                             'in Distance constructor')
        elif unit is None:
            raise u.UnitsError('No unit was provided to Distance constructor')
        #"else" the baseline `value` + `unit` case

        unit = _convert_to_and_validate_length_unit(unit)

        try:
            value = np.asarray(value)
        except ValueError as e:
            raise TypeError(str(e))

        if value.dtype.kind not in 'iuf':
            raise TypeError("Unsupported dtype '{0}'".format(value.dtype))

        return super(Distance, cls).__new__(cls, value, unit, dtype=dtype,
                                            copy=copy)

    def __quantity_view__(self, obj, unit):
        unit = _convert_to_and_validate_length_unit(unit)
        return super(Distance, self).__quantity_view__(obj, unit)

    def __quantity_instance__(self, val, unit, **kwargs):
        unit = _convert_to_and_validate_length_unit(unit)
        return super(Distance, self).__quantity_instance__(val, unit, **kwargs)


    @property
    def z(self):
        """Short for ``self.compute_z()``"""
        return self.compute_z()

    def compute_z(self, cosmology=None):
        """
        The redshift for this distance assuming its physical distance is
        a luminosity distance.

        Parameters
        ----------
        cosmology : `~astropy.cosmology.cosmology` or None
            The cosmology to assume for this calculation, or None to use the
            current cosmology.

        Returns
        -------
        z : float
            The redshift of this distance given the provided `cosmology`.
        """
        from ..cosmology import luminosity_distance
        from scipy import optimize

        # FIXME: array: need to make this calculation more vector-friendly

        f = lambda z, d, cos: (luminosity_distance(z, cos).value - d) ** 2
        return optimize.brent(f, (self.Mpc, cosmology))

    @property
    def distmod(self):
        """  The distance modulus of this distance as a Quantity """
        val = 5. * np.log10(self.to(u.pc).value) - 5.
        return u.Quantity(val, u.mag)

    @staticmethod
    def _distmod_to_pc(dm):
        return 10 ** ((dm + 5) / 5.)

    #these might be included in future revisions of Quantity depending on how
    #the automatic conversion members are implemented, but make sure they're
    #always available
    @property
    def pc(self):
        return self.to(u.parsec).value

    @property
    def kpc(self):
        return self.to(u.kiloparsec).value

    @property
    def Mpc(self):
        return self.to(u.megaparsec).value

    @property
    def lyr(self):
        return self.to(u.lightyear).value

    @property
    def km(self):
        return self.to(u.kilometer).value


class CartesianPoints(u.Quantity):
    """
    A cartesian representation of a point in three-dimensional space.

    Parameters
    ----------
    xorarr : `~astropy.units.Quantity` or array-like
        The first cartesian coordinate or a single array or
        `~astropy.units.Quantity` where the first dimension is length-3.
    y : `~astropy.units.Quantity` or array-like, optional
        The second cartesian coordinate.
    z : `~astropy.units.Quantity` or array-like, optional
        The third cartesian coordinate.
    unit : `~astropy.units.UnitBase` object or None
        The physical unit of the coordinate values. If `x`, `y`, or `z`
        are quantities, they will be converted to this unit.
    dtype : ~numpy.dtype, optional
        See `~astropy.units.Quantity`. Must be given as a keyword argument.
    copy : bool, optional
        See `~astropy.units.Quantity`. Must be given as a keyword argument.

    Raises
    ------
    astropy.units.UnitsError
        If the units on `x`, `y`, and `z` do not match
    ValueError
        If `y` and `z` don't match `xorarr`'s shape or `xorarr` is not length-3
    TypeError
        If incompatible array types are passed into `xorarr`, `y`, or `z`

    """

    def __new__(cls, xorarr, y=None, z=None, unit=None, dtype=None, copy=True):
        if y is None and z is None:
            if len(xorarr) != 3:
                raise ValueError('input to CartesianPoints is not length 3')

            qarr = xorarr
        elif y is not None and z is not None:
            x = xorarr

            if unit is None:
                #they must all much units or this fails
                for coo in (x, y, z):
                    if isinstance(coo, u.Quantity):
                        if unit is not None and coo.unit != unit:
                            raise u.UnitsError('Units for `x`, `y`, and `z` do '
                                               'not match in CartesianPoints')
                        unit = coo.unit
                #if `unit`  is still None at this point, it means none were
                #Quantties, which is fine, because it means the user wanted
                #the unit to be None
            else:
                #convert them all to the given coordinate
                if isinstance(x, u.Quantity):
                    x = x.to(unit)
                if isinstance(y, u.Quantity):
                    y = y.to(unit)
                if isinstance(z, u.Quantity):
                    z = z.to(unit)

            qarr = [np.asarray(coo) for coo in (x, y, z)]
            if not (x.shape == y.shape == z.shape):
                raise ValueError("shapes for x,y, and z don't match in "
                                 "CartesianPoints")
                #let the unit be whatever it is

        else:
            raise TypeError('Must give all of x,y, and z or just array in '
                            'CartesianPoints')

        if unit is not None:
            unit = _convert_to_and_validate_length_unit(unit)

        try:
            qarr = np.asarray(qarr)
        except ValueError as e:
            raise TypeError(str(e))

        if qarr.dtype.kind not in 'iuf':
            raise TypeError("Unsupported dtype '{0}'".format(qarr.dtype))

        return super(CartesianPoints, cls).__new__(cls, qarr, unit, dtype=dtype,
                                            copy=copy)

    def __quantity_view__(self, obj, unit):
        if unit is not None:
            unit = _convert_to_and_validate_length_unit(unit)
        return super(CartesianPoints, self).__quantity_view__(obj, unit)

    def __quantity_instance__(self, val, unit, **kwargs):
        if unit is not None:
            unit = _convert_to_and_validate_length_unit(unit)
        return super(CartesianPoints, self).__quantity_instance__(val, unit, **kwargs)

    @property
    def x(self):
        """
        The second cartesian coordinate as a `~astropy.units.Quantity`.
        """
        return self[0]

    @property
    def y(self):
        """
        The second cartesian coordinate as a `~astropy.units.Quantity`.
        """
        return self[1]

    @property
    def z(self):
        """
        The third cartesian coordinate as a `~astropy.units.Quantity`.
        """
        return self[2]

    def to_spherical(self):
        """
        Converts to the spherical representation of this point.

        Returns
        -------
        r : astropy.units.Quantity
            The radial coordinate (in the same units as this `CartesianPoint`).
        lat : astropy.units.Quantity
            The spherical coordinates latitude.
        lon : astropy.units.Quantity
            The spherical coordinates longitude.

        """
        from .angles import Latitude, Longitude

        rarr, latarr, lonarr = cartesian_to_spherical(self.x, self.y, self.z)

        r = Distance(rarr, unit=self.unit)
        lat = Latitude(latarr, unit=u.radians)
        lon = Longitude(lonarr, unit=u.radians)

        return r, lat, lon

    def __repr__(self):
        return '<CartesianPoints ({x}, {y}, {z}) {unit}>'.format(x=self.x,
                y=self.y, z=self.z, unit=self.unit)


def _convert_to_and_validate_length_unit(unit):
    """
    raises `astropy.units.UnitsError` if not a length unit
    """
    if unit is not None:
        unit = u.Unit(unit)

    if not unit.is_equivalent(u.kpc):
        raise u.UnitsError(six.u('Unit "{0}" is not a length type').format(unit))
    return unit

#<------------transformation-related utility functions----------------->


def cartesian_to_spherical(x, y, z):
    """
    Converts 3D rectangular cartesian coordinates to spherical polar
    coordinates.

    Note that the resulting angles are latitude/longitude or
    elevation/azimuthal form.  I.e., the origin is along the equator
    rather than at the north pole.

    .. note::
        This is a low-level function used internally in
        `astropy.coordinates`.  It is provided for users if they really
        want to use it, but it is recommended that you use the
        `astropy.coordinates` coordinate systems.

    Parameters
    ----------
    x : scalar or array-like
        The first cartesian coordinate.
    y : scalar or array-like
        The second cartesian coordinate.
    z : scalar or array-like
        The third cartesian coordinate.

    Returns
    -------
    r : float or array
        The radial coordinate (in the same units as the inputs).
    lat : float or array
        The latitude in radians
    lon : float or array
        The longitude in radians
    """
    import math

    xsq = x ** 2
    ysq = y ** 2
    zsq = z ** 2

    r = (xsq + ysq + zsq) ** 0.5
    s = (xsq + ysq) ** 0.5

    if np.isscalar(x) and np.isscalar(y) and np.isscalar(z):
        lon = math.atan2(y, x)
        lat = math.atan2(z, s)
    else:
        lon = np.arctan2(y, x)
        lat = np.arctan2(z, s)

    return r, lat, lon


def spherical_to_cartesian(r, lat, lon):
    """
    Converts spherical polar coordinates to rectangular cartesian
    coordinates.

    Note that the input angles should be in latitude/longitude or
    elevation/azimuthal form.  I.e., the origin is along the equator
    rather than at the north pole.

    .. note::
        This is a low-level function used internally in
        `astropy.coordinates`.  It is provided for users if they really
        want to use it, but it is recommended that you use the
        `astropy.coordinates` coordinate systems.

    Parameters
    ----------
    r : scalar or array-like
        The radial coordinate (in the same units as the inputs).
    lat : scalar or array-like
        The latitude in radians
    lon : scalar or array-like
        The longitude in radians

    Returns
    -------
    x : float or array
        The first cartesian coordinate.
    y : float or array
        The second cartesian coordinate.
    z : float or array
        The third cartesian coordinate.


    """
    import math

    if np.isscalar(r) and np.isscalar(lat) and np.isscalar(lon):
        x = r * math.cos(lat) * math.cos(lon)
        y = r * math.cos(lat) * math.sin(lon)
        z = r * math.sin(lat)
    else:
        x = r * np.cos(lat) * np.cos(lon)
        y = r * np.cos(lat) * np.sin(lon)
        z = r * np.sin(lat)

    return x, y, z
