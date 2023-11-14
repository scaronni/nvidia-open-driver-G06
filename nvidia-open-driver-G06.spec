#
# spec file for package nvidia-Open-gfxG06
#
# Copyright (c) 2022 SUSE LLC
#
# All modifications and additions to the file contributed by third parties
# remain the property of their copyright owners, unless otherwise agreed
# upon. The license for this file, and modifications and additions to the
# file, is the same license as for the pristine package itself (unless the
# license for the pristine package is not an Open Source License, in which
# case the license is the MIT License). An "Open Source License" is a
# license that conforms to the Open Source Definition (Version 1.9)
# published by the Open Source Initiative.

# Please submit bugfixes or comments via https://bugs.opensuse.org/
#

%if %{undefined kernel_module_directory}
%if 0%{?usrmerged}
%define kernel_module_directory /usr/lib/modules
%else
%define kernel_module_directory /lib/modules
%endif
%endif

%if 0%{?suse_version} >= 1550 || 0%{?sle_version} >= 150400
%define compress_modules zstd
%else
%define compress_modules xz
%endif
Name:           nvidia-open-driver-G06
Version:        545.29.02
Release:        0
Summary:        NVIDIA open kernel module driver for GeForce RTX 2000 series and newer
License:        GPL-2.0 and MIT
Group:          System/Kernel
URL:            https://github.com/NVIDIA/open-gpu-kernel-modules/
Source0:        open-gpu-kernel-modules-%{version}.tar.gz
Source1:        my-find-supplements
Source2:        pci_ids-%{version}
Source3:        kmp-filelist
Source4:        kmp-post.sh
Source5:        kmp-postun.sh
Source6:        modprobe.nvidia.install
Source7:        preamble
Source8:        json-to-pci-id-list.py
Source9:        kmp-preun.sh
Source10:       kmp-trigger.sh
Source11:       nvidia-open-driver-G06.rpmlintrc
Patch0:         0001-Don-t-override-INSTALL_MOD_DIR.patch
Patch2:         persistent-nvidia-id-string.patch
BuildRequires:  %{kernel_module_package_buildreqs}
BuildRequires:  gcc-c++
BuildRequires:  kernel-source
BuildRequires:  kernel-syms
BuildRequires:  perl-Bootloader
BuildRequires:  zstd
%ifnarch aarch64
%if !0%{?is_opensuse} 
BuildRequires:  kernel-syms-azure
%endif
%endif
ExclusiveArch:  x86_64 aarch64

%if 0%{!?kmp_template_name:1}
%define kmp_template_name /usr/lib/rpm/kernel-module-subpackage
%endif

# Tumbleweed uses %triggerin instead of %post script in order to generate
# and install kernel module
%if 0%{?suse_version} >= 1550 && 0%{?is_opensuse}
%(sed -e '/^%%preun\>/ r %_sourcedir/kmp-preun.sh' -e '/^%%postun\>/ r %_sourcedir/kmp-postun.sh' -e '/^Provides: multiversion(kernel)/d' %kmp_template_name >%_builddir/nvidia-kmp-template)
%(echo "%triggerin -n %%{-n*}-kmp-%1 -- kernel-default-devel" >> %_builddir/nvidia-kmp-template)
%(cat %_sourcedir/kmp-preun.sh               >> %_builddir/nvidia-kmp-template)
%(cat %_sourcedir/kmp-trigger.sh             >> %_builddir/nvidia-kmp-template)
# Let all initrds get generated by regenerate-initrd-posttrans
# if kernel-<flavor>-devel gets updated
%(echo "%%{?regenerate_initrd_posttrans}"  >> %_builddir/nvidia-kmp-template)
%else
%(sed -e '/^%%post\>/ r %_sourcedir/kmp-post.sh' -e '/^%%preun\>/ r %_sourcedir/kmp-preun.sh' -e '/^%%postun\>/ r %_sourcedir/kmp-postun.sh' -e '/^Provides: multiversion(kernel)/d' %kmp_template_name >%_builddir/nvidia-kmp-template)
# moved from %kmp_post snippet to this place (boo#1145316)
%(sed -i '/^%%posttrans/i \
exit $RES' %_builddir/nvidia-kmp-template)
%endif
%kernel_module_package -n %{name} -t %_builddir/nvidia-kmp-template -f %_sourcedir/kmp-filelist -p %_sourcedir/preamble

# create hardware supplements
%define __kmp_supplements %_sourcedir/my-find-supplements %_sourcedir/pci_ids-%{version}

# newer rpmbuilds attach the kernel version and the major part of release to %%pci_id_file of the __kmp_supplements script
# boo#1190210
%define kbuildver %(rpm -q --queryformat '%%{VERSION}_%%{RELEASE}' kernel-syms | sed -n 's/\\(.*\\)\\.[0-9]\\{1,\\}/\\1/p')

%description
This package provides the open-source NVIDIA kernel module driver
for GeForce RTX 2000 series and newer GPUs.

%prep
%setup -q -n open-gpu-kernel-modules-%{version}
%patch0 -p1
%patch2 -p1
set -- *
mkdir source
mv "$@" source/
mkdir obj

pushd %_sourcedir
chmod 755 my-find-supplements*
# symlink the %pci_id_file to the one, that rpmbuild generates, to enable my-find-supplement to succeed properly
# boo#1190210
ln -sv pci_ids-%{version} pci_ids-%{version}_k%{kbuildver}
popd

%build
%ifarch aarch64
# -Wall is upstream default
export CFLAGS="-Wall -mno-outline-atomics"
%endif
# kernel was compiled using a different compiler
export CC=gcc
# no longer needed and never worked anyway (it was only a stub) [boo#1211892]
export NV_EXCLUDE_KERNEL_MODULES=nvidia-peermem
for flavor in %{flavors_to_build}; do
        rm -rf obj/$flavor
        cp -r source obj/$flavor
	pushd obj/$flavor
	if [ -d /usr/src/linux-$flavor ]; then
	  export SYSSRC=/usr/src/linux-$flavor
	else
	  export SYSSRC=/usr/src/linux
	fi
	export SYSOUT=/usr/src/linux-obj/%_target_cpu/$flavor
        make %{?_smp_mflags} %{?linux_make_arch} modules
        popd
done

%install
### do not sign the ghost .ko file, it is generated on target system anyway
export BRP_PESIGN_FILES=""
export INSTALL_MOD_PATH=%{buildroot}
export INSTALL_MOD_DIR=updates
for flavor in %{flavors_to_build}; do
	pushd obj/$flavor
	if [ -d /usr/src/linux-$flavor ]; then
	  export SYSSRC=/usr/src/linux-$flavor
	else
	  export SYSSRC=/usr/src/linux
	fi
	export SYSOUT=/usr/src/linux-obj/%_target_cpu/$flavor
        make %{?linux_make_arch} modules_install
	popd
        mkdir -p %{buildroot}/usr/src/kernel-modules/nvidia-%{version}-${flavor}
        cp -r source/* %{buildroot}/usr/src/kernel-modules/nvidia-%{version}-${flavor}
done

%if 0%{?suse_version} >= 1550
MODPROBE_DIR=%{buildroot}/usr/lib/modprobe.d
%else
MODPROBE_DIR=%{buildroot}%{_sysconfdir}/modprobe.d
%endif

mkdir -p $MODPROBE_DIR
for flavor in %flavors_to_build; do
    cat > $MODPROBE_DIR/50-nvidia-$flavor.conf << EOF
blacklist nouveau
options nvidia NVreg_DeviceFileUID=0 NVreg_DeviceFileGID=33 NVreg_DeviceFileMode=0660 NVreg_PreserveVideoMemoryAllocations=1
options nvidia-drm modeset=1 fbdev=1
EOF
    echo -n "install nvidia " >> $MODPROBE_DIR/50-nvidia-$flavor.conf
    tail -n +3 %_sourcedir/modprobe.nvidia.install | awk '{ printf "%s ", $0 }' >> $MODPROBE_DIR/50-nvidia-$flavor.conf
# otherwise nvidia-uvm is missing in initrd and won't get loaded when nvidia
# module is loaded in initrd; so better let's load all the nvidia modules
# later ...
%if 0%{?suse_version} >= 1550
  mkdir -p %{buildroot}/usr/lib/dracut/dracut.conf.d
  cat  >   %{buildroot}/usr/lib/dracut/dracut.conf.d/60-nvidia-$flavor.conf << EOF
%else
  mkdir -p %{buildroot}/etc/dracut.conf.d
  cat  > %{buildroot}/etc/dracut.conf.d/60-nvidia-$flavor.conf << EOF
%endif
omit_drivers+=" nvidia nvidia-drm nvidia-modeset nvidia-uvm "
EOF
done

