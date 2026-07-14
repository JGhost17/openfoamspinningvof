cd ~/mixingTank/constant/triSurface
for f in ami.stl impeller.stl tank.stl; do
  cp "$f" "${f%.stl}.STL"
done
ls -la