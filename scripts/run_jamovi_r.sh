#!/bin/sh
# Runs an R script with the R and jmv modules bundled in /Applications/jamovi.app
R_HOME=/Applications/jamovi.app/Contents/Frameworks/R.framework/Versions/4.5-arm64/Resources
M=/Applications/jamovi.app/Contents/Resources/modules
export R_HOME DYLD_FALLBACK_LIBRARY_PATH="$R_HOME/lib" R_LIBS="$M/jmv/R:$M/base/R"
script=$1; shift
exec "$R_HOME/bin/exec/R" --vanilla --slave -f "$script" --args "$@"
