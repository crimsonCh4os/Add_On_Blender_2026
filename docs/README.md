# Documentación del proyecto

Esta carpeta contiene la documentación LaTeX de la suite de add-ons para Blender.

## Documentos principales

- `memoria.tex`: documento principal de la memoria.
- `anexos.tex`: documento principal de los anexos.
- `tex/`: capítulos y anexos incluidos desde los documentos principales.
- `diagramas/`: imágenes y diagramas utilizados en la documentación.
- `img/`: recursos gráficos de la plantilla.
- `bibliografia.bib` y `bibliografiaAnexos.bib`: bibliografía de memoria y anexos.

## Compilación

Desde esta carpeta puede compilarse la documentación con:

```bash
pdflatex -interaction=nonstopmode -halt-on-error memoria.tex
bibtex memoria
pdflatex -interaction=nonstopmode -halt-on-error memoria.tex
pdflatex -interaction=nonstopmode -halt-on-error memoria.tex

pdflatex -interaction=nonstopmode -halt-on-error anexos.tex
bibtex anexos
pdflatex -interaction=nonstopmode -halt-on-error anexos.tex
pdflatex -interaction=nonstopmode -halt-on-error anexos.tex
```

Si no se modifica la bibliografía, normalmente basta con ejecutar `pdflatex` sobre `memoria.tex` y `anexos.tex`.

## Archivos generados

Los archivos auxiliares de LaTeX (`.aux`, `.log`, `.toc`, `.lof`, `.lot`, `.out`, `.bbl`, `.blg`, etc.) son productos de compilación. Pueden borrarse y regenerarse en cualquier momento.

Los PDF finales (`memoria.pdf` y `anexos.pdf`) pueden conservarse si forman parte de la entrega.
