#!/usr/bin/env python3

# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# This Swarming bot test script uses gapit to perform a capture-replay test,
# checking whether the replay output matches the app frames.

import argparse
import botutil
import json
import os
import subprocess
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('agi_dir', help='Path to AGI build')
    parser.add_argument('out_dir', help='Path to output directory')
    args = parser.parse_args()

    #### Early checks and sanitization
    assert os.path.isdir(args.agi_dir)
    agi_dir = os.path.normpath(args.agi_dir)
    assert os.path.isdir(args.out_dir)
    out_dir = os.path.normpath(args.out_dir)

    #### Test parameters
    test_params = {
        'startframe': '100',
        'numframes': '5',
        'observe_frames': '1',
        'api': 'vulkan',
    }
    required_keys = ['apk', 'package', 'activity']
    botutil.load_params(test_params, required_keys=required_keys)

    #### Install APK
    botutil.install_apk(test_params)

    #### Trace the app
    gapit = os.path.join(agi_dir, 'gapit')
    gfxtrace = os.path.join(out_dir, test_params['package'] + '.gfxtrace')
    cmd = [
        gapit, 'trace',
        '-api', test_params['api'],
        '-start-at-frame', test_params['startframe'],
        '-capture-frames', test_params['numframes'],
        '-observe-frames', test_params['observe_frames'],
        '-out', gfxtrace
    ]

    if 'additionalargs' in test_params.keys():
        cmd += ['-additionalargs', test_params['additionalargs']]

    cmd += [test_params['package'] + '/' + test_params['activity']]

    p = botutil.runcmd(cmd)
    if p.returncode != 0:
        return 1

    #### Stop the app asap for device cool-down
    botutil.adb(['shell', 'am', 'force-stop', test_params['package']])

    #### Replay
    # Use the 'sxs-frames' mode that generates a series of PNGs rather
    # than an mp4 video. This makes inspection easier, and removes the
    # dependency on ffmpeg on the running hosts.
    videooutfile = os.path.join(out_dir, test_params['package'] + '.frame.png')
    cmd = [
        gapit, 'video',
        '-gapir-nofallback',
        '-type', 'sxs-frames',
        '-frames-minimum', test_params['numframes'],
        '-out', videooutfile,
        gfxtrace
    ]
    p = botutil.runcmd(cmd)
    if p.returncode != 0:
        return p.returncode

    #### Screenshot test to retrieve mid-frame resources
    screenshotfile = os.path.join(out_dir, test_params['package'] + '.png')
    cmd = [
        gapit, 'screenshot',
        '-executeddraws', '5',
        '-out', screenshotfile,
        gfxtrace
    ]
    p = botutil.runcmd(cmd)
    if p.returncode != 0:
        return p.returncode

    #### Frame profiler
    # Check that frame profiling generates valid JSON
    profile_json = os.path.join(out_dir, test_params['package'] + '.profiling.json')
    cmd = [
        gapit, 'profile',
        '-json',
        '-out', profile_json,
        gfxtrace
    ]
    p = botutil.runcmd(cmd)
    if p.returncode != 0:
        return p.returncode
    assert botutil.is_valid_json(profile_json)

    #### Frame graph
    # Check that framegraph generates valid JSON
    framegraph_json = os.path.join(out_dir, test_params['package'] + '.framegraph.json')
    cmd = [
        gapit, 'framegraph',
        '-json', framegraph_json,
        gfxtrace
    ]
    p = botutil.runcmd(cmd)
    if p.returncode != 0:
        return p.returncode
    assert botutil.is_valid_json(framegraph_json)

    #### All tests have passed, return success
    return 0

if __name__ == '__main__':
    sys.exit(main())
