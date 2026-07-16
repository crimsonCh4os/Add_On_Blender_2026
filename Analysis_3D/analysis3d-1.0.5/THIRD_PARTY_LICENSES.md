# Third-party dependencies

Analysis 3D does **not** bundle the following libraries in its source repository.
They are downloaded by the user from the Python Package Index through an
explicit **Install dependencies / Instalar dependencias** action.

- NumPy — BSD-3-Clause
- Matplotlib — PSF-based license

Matplotlib may install transitive dependencies such as ContourPy, Cycler,
FontTools, Kiwisolver, Packaging, Pillow, PyParsing and Python-dateutil.
Their license files are supplied within the packages downloaded by `pip`.

Always verify the licenses of the exact versions used before redistribution.
