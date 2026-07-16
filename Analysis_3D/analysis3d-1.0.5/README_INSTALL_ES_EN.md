# Analysis 3D — Installation / Instalación

## Español

### Instalación recomendada con instalador externo (Windows)

1. En Blender, abre **Edit > Preferences > Add-ons**.
2. Pulsa **Install from Disk** y selecciona `analysis3d-1.0.5.zip`.
3. Cierra Blender.
4. Extrae la carpeta `Installer_Windows` y ejecuta `install_dependencies_windows.bat`.
5. El instalador detectará Blender y la carpeta del complemento. Si hay varias instalaciones, te pedirá elegir una.
6. Vuelve a abrir Blender y activa **Analysis 3D**.

El instalador usa el Python incluido con Blender y guarda NumPy y Matplotlib en
la carpeta privada `site-packages` del complemento. Blender y las dependencias
no se incluyen en el repositorio.

### Alternativa desde Blender

Si faltan bibliotecas, el panel **3D Analysis** también permite pulsar
**Instalar dependencias**. Reinicia Blender al terminar.

## English

### Recommended external installer (Windows)

1. In Blender, open **Edit > Preferences > Add-ons**.
2. Choose **Install from Disk** and select `analysis3d-1.0.5.zip`.
3. Close Blender.
4. Extract `Installer_Windows` and run `install_dependencies_windows.bat`.
5. The installer detects Blender and the add-on folder. If it finds multiple installations, it asks you to choose one.
6. Reopen Blender and enable **Analysis 3D**.

The installer uses Blender's bundled Python and stores NumPy and Matplotlib in
the add-on's private `site-packages` folder. Blender and third-party packages
are not included in the repository.

### Blender fallback

When libraries are missing, the **3D Analysis** panel can also run
**Install dependencies**. Restart Blender afterwards.
