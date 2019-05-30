# -*- coding: utf-8 -*-
"""
GStools subpackage providing a class for simple kriging.

.. currentmodule:: gstools.krige.simple

The following classes are provided

.. autosummary::
   Simple
"""
# pylint: disable=C0103
from __future__ import division, absolute_import, print_function

from functools import partial

import numpy as np
from scipy.linalg import inv
from scipy.spatial.distance import cdist

from gstools.covmodel.base import CovModel
from gstools.field.tools import (
    check_mesh,
    make_isotropic,
    unrotate_mesh,
    reshape_axis_from_struct_to_unstruct,
    reshape_field_from_unstruct_to_struct,
)
from gstools.tools.geometric import pos2xyz, xyz2pos
from gstools.tools.export import vtk_export as vtk_ex
from gstools.krige.krigesum import krigesum

__all__ = ["Simple"]


class Simple(object):
    """
    A class for simple kriging.

    Parameters
    ----------
    model : :any:`CovModel`
        Covariance Model used for kriging.
    mean : :class:`float`, optional
        mean value of the kriging field
    cond_pos : :class:`list`
        tuple, containing the given condition positions (x, [y, z])
    cond_val : :class:`numpy.ndarray`
        the values of the conditions
    """

    def __init__(self, model, mean, cond_pos, cond_val):
        # initialize private attributes
        self.field = None
        self.error = None
        self.mean = mean

        self._model = None
        self._cond_pos = None
        self._cond_val = None

        self.model = model
        self.set_condition(cond_pos, cond_val)

        # initialize attributes

    def __call__(self, pos, mesh_type="unstructured"):
        """
        Generate the simple kriging field.

        The field is saved as `self.field` and is also returned.

        Parameters
        ----------
        pos : :class:`list`
            the position tuple, containing main direction and transversal
            directions (x, [y, z])
        mesh_type : :class:`str`
            'structured' / 'unstructured'

        Returns
        -------
        field : :class:`numpy.ndarray`
            the kriged field
        error : :class:`numpy.ndarray`
            the kriging error
        """
        # internal conversation
        x, y, z = pos2xyz(pos, dtype=np.double)
        c_x, c_y, c_z = pos2xyz(self.cond_pos, dtype=np.double)
        self.pos = xyz2pos(x, y, z)
        self.mesh_type = mesh_type
        # format the positional arguments of the mesh
        check_mesh(self.model.dim, x, y, z, mesh_type)
        mesh_type_changed = False
        if mesh_type == "structured":
            mesh_type_changed = True
            mesh_type_old = mesh_type
            mesh_type = "unstructured"
            x, y, z, axis_lens = reshape_axis_from_struct_to_unstruct(
                self.model.dim, x, y, z
            )
        if self.model.do_rotation:
            x, y, z = unrotate_mesh(self.model.dim, self.model.angles, x, y, z)
            c_x, c_y, c_z = unrotate_mesh(
                self.model.dim, self.model.angles, c_x, c_y, c_z
            )
        y, z = make_isotropic(self.model.dim, self.model.anis, y, z)
        c_y, c_z = make_isotropic(self.model.dim, self.model.anis, c_y, c_z)

        # set condtions to zero mean
        cond = self.cond_val - self.mean
        krig_mat = inv(self._get_cov_mat((c_x, c_y, c_z), (c_x, c_y, c_z)))
        krig_vecs = self._get_cov_mat((c_x, c_y, c_z), (x, y, z))
        # generate the kriged field
        field, error = krigesum(krig_mat, krig_vecs, cond)

        # reshape field if we got an unstructured mesh
        if mesh_type_changed:
            mesh_type = mesh_type_old
            field = reshape_field_from_unstruct_to_struct(
                self.model.dim, field, axis_lens
            )
            error = reshape_field_from_unstruct_to_struct(
                self.model.dim, error, axis_lens
            )
        # calculate the kriging error
        self.error = self.model.sill - error
        # add the given mean
        self.field = field + self.mean
        return self.field, self.error

    def _get_cov_mat(self, pos1, pos2):
        return self.model.cov_nugget(
            cdist(
                np.column_stack(pos1[: self.model.dim]),
                np.column_stack(pos2[: self.model.dim]),
            )
        )

    def vtk_export(self, filename, fieldname="field"):  # pragma: no cover
        """Export the stored field to vtk.

        Parameters
        ----------
        filename : :class:`str`
            Filename of the file to be saved, including the path. Note that an
            ending (.vtr or .vtu) will be added to the name.
        fieldname : :class:`str`, optional
            Name of the field in the VTK file. Default: "field"
        """
        if not (
            self.pos is None or self.field is None or self.mesh_type is None
        ):
            vtk_ex(filename, self.pos, self.field, fieldname, self.mesh_type)
        else:
            print("gstools.SRF.vtk_export: No field stored in the srf class.")

    def plot(self, field="field", fig=None, ax=None):
        """
        Plot the stored field.

        Parameters
        ----------
        field : :class:`str`, optional
            Field that should be plotted. Default: "field"
        fig : :any:`Figure` or :any:`None`
            Figure to plot the axes on. If `None`, a new one will be created.
            Default: `None`
        ax : :any:`Axes` or :any:`None`
            Axes to plot on. If `None`, a new one will be added to the figure.
            Default: `None`
        """
        from gstools.field.plot import plot_srf

        plot_srf(self, field, fig, ax)

    def set_condition(self, cond_pos, cond_val):
        """Set the conditions for kriging.

        Parameters
        ----------
        cond_pos : :class:`list`
            the position tuple of the conditions (x, [y, z])
        cond_val : :class:`numpy.ndarray`
            the values of the conditions
        """
        self._cond_pos = cond_pos
        self._cond_val = np.array(cond_val, dtype=np.double)

    def structured(self, *args, **kwargs):
        """Simple kriging on a structured mesh.

        See :any:`Simple.__call__`
        """
        call = partial(self.__call__, mesh_type="structured")
        return call(*args, **kwargs)

    def unstructured(self, *args, **kwargs):
        """Simple kriging on an unstructured mesh.

        See :any:`Simple.__call__`
        """
        call = partial(self.__call__, mesh_type="unstructured")
        return call(*args, **kwargs)

    @property
    def cond_pos(self):
        """:class:`list`: The position tuple of the conditions."""
        return self._cond_pos

    @property
    def cond_val(self):
        """:class:`list`: The values of the conditions."""
        return self._cond_val

    @property
    def model(self):
        """:any:`CovModel`: The covariance model used for kriging."""
        return self._model

    @model.setter
    def model(self, model):
        if isinstance(model, CovModel):
            self._model = model
        else:
            raise ValueError(
                "gstools.krige.Simple: "
                + "'model' is not an instance of 'gstools.CovModel' "
                + str(model)
            )

    def __str__(self):
        """Return String representation."""
        return self.__repr__()

    def __repr__(self):
        """Return String representation."""
        return "Simple(model={0}, mean={1}, cond_pos={2}, cond_val={3}".format(
            self.model, self.mean, self.cond_pos, self.cond_val
        )


if __name__ == "__main__":  # pragma: no cover
    import doctest

    doctest.testmod()
