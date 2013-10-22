svn up
svn ci -m "Checking in before pushing staging to production"
rsync --dry-run --exclude=.svn -ruv rhel6w-complete-staging-x86_64/ rhel6w-complete-x86_64/
svn ci -m "Pushed staging groups to production"
./gengroup.py

