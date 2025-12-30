# OBS Video Scheduler

Library and web application for managing pre-recorded videos playbacks in [Open Broadcaster Software](https://obsproject.com/) broadcasts.

## obs-video-scheduler

Python + web application that enables scheduling of pre-recorded video playbacks during OBS broadcasts. Scheduled videos automatically start in the configured scene/layer via obs-websocket.

Currently two interfaces are supported:
- web interface for schedule management and settings (http://localhost:8080)
- web interface with upcoming video announcements (http://localhost:8080/comm) that can be used by commentators or broadcast director

## Installation and usage
Currently the only supported platform is Windows and 64-bit OBS. It's likely that it can be easily ported to other platforms.

See detailed installation and usage instructions [here](docs/INSTALL.md).

[Video walkthrough](https://www.youtube.com/watch?v=nvNznDg5yh4)

## License
Project is distributed under Apache License. See LICENSE [file](LICENSE) for details.

## Acknowledgements
Project was created for [ICPC](https://icpc.baylor.edu/), the largest worlwide college student programming competition.
It's been used during [ICPC Live](http://live.icpc.global/) broadcasts since 2016.

obs-video-scheduler is built based on [TimeSlider Plugin for jQuery](https://github.com/v-v-vishnevskiy/timeslider) distributed under The MIT License.

## Contacts
Reach out to me at krotkov.pavel@gmail.com
