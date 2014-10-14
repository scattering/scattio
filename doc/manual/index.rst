.. _manual:

###############
Data Readers
###############

.. currentmodule:: scattio

File formats
============

.. toctree::
   :maxdepth: 2

   bt7format_description.rst
   sansformat_description.rst

Format registry
===============

.. autosummary::
   :toctree: module

   registry
   formats


File readers
============


.. autosummary::
   :toctree: module

   h5nexus
   ncnr.iceformat
   ncnr.icpformat
   ncnr.sansformat

File converters
===============

.. autosummary::
   :toctree: module

   bt7nxs
   ng7nxs
   sansnxs

Internal functions
==================

.. autosummary::
   :toctree: module

   wrte_nexus
   iso8601
   jsonutil
   qxqz
   unit
   utils
   ncnr.scanparser

