// Inspect only the explicitly supplied test event node; never grab it.
#include <libinput.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>
static int op(const char *p,int flags,void *data){return strcmp(p,data)?-1:open(p,flags);}
static void cl(int fd,void *data){(void)data;close(fd);}
int main(int argc,char **argv){if(argc!=2)return 2;struct libinput_interface i={op,cl};struct libinput *l=libinput_path_create_context(&i,argv[1]);struct libinput_device*d=libinput_path_add_device(l,argv[1]);if(!d)return 3;printf("name=%s touch=%d pointer=%d keyboard=%d\n",libinput_device_get_name(d),libinput_device_has_capability(d,LIBINPUT_DEVICE_CAP_TOUCH),libinput_device_has_capability(d,LIBINPUT_DEVICE_CAP_POINTER),libinput_device_has_capability(d,LIBINPUT_DEVICE_CAP_KEYBOARD));int ok=!strcmp(libinput_device_get_name(d),"TouchDeck-Test")&&libinput_device_has_capability(d,LIBINPUT_DEVICE_CAP_TOUCH)&&!libinput_device_has_capability(d,LIBINPUT_DEVICE_CAP_POINTER);libinput_unref(l);return ok?0:4;}
