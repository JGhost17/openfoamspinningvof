source /usr/lib/openfoam/openfoam2406/etc/bashrc
blockMesh -help 2>&1 | head -3
echo ---
snappyHexMesh -help 2>&1 | head -3
echo ---
echo $WM_PROJECT_VERSION