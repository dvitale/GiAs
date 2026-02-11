git rm -rf .git
git add .
git commit -m "."
git branch -M main
git push -u origin main
git remote add origin https://github.com/dvitale/GiAs.git
git push -u origin main -f
