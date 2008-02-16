#!/bin/sh

export PYTHONPATH=$SUGAR_BUNDLE_PATH/site-packages:$PYTHONPATH
export LD_LIBRARY_PATH=$SUGAR_BUNDLE_PATH/lib:$LD_LIBRARY_PATH
export LD_PRELOAD=$SUGAR_BUNDLE_PATH/lib/libgtksourceview-1.0.so

sugar-activity develop_app.DevelopActivity -s $@

