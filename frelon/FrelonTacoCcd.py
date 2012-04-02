############################################################################
# This file is part of LImA, a Library for Image Acquisition
#
# Copyright (C) : 2009-2011
# European Synchrotron Radiation Facility
# BP 220, Grenoble 38043
# FRANCE
#
# This is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.
############################################################################
from Lima import Frelon
from TacoCcd import *
import gc

DebParams.setTypeFlags(DebParams.AllFlags)
DebParams.setModuleFlags(DebParams.AllFlags)
DebParams.setFormatFlags(DebParams.AllFlags)

class FrelonTacoAcq(TacoCcdAcq):

    DEB_CLASS(DebModApplication, "FrelonTacoAcq")

    GetAcqFrames   = 0x02
    DisableE2VCorr = 0x10

    LiveNbConcatFrames = 16
    
    StateDesc = {
        DEVFAULT:        'Fault: Camera off or disconnected',
        DevCcdReady:     'Ready: Camera is Idle',
        DevCcdAcquiring: 'Acquiring: Camera is Running',
    }

    DefaultResources = {
        'espia_dev_nb': 0,
    }
    
    @DEB_MEMBER_FUNCT
    def __init__(self, dev_name, dev_class=None, cmd_list=None):
        TacoCcdAcq.__init__(self, dev_name, dev_class, cmd_list)

        res_pars = self.getResources(self.DefaultResources)
        espia_dev_nb = int(res_pars['espia_dev_nb'])
        
        self.m_acq = Frelon.FrelonAcq(espia_dev_nb)
        self.m_get_acq_frames = False

    @DEB_MEMBER_FUNCT
    def __del__(self):
        pass

    @TACO_SERVER_FUNCT
    def reset(self):
        self.m_acq.reset()

    @TACO_SERVER_FUNCT
    def getState(self):
        deb.Trace('Query device state ...')
        ct_status = self.m_acq.getStatus()
        acq_status = ct_status.AcquisitionStatus
        if acq_status == AcqRunning:
            self.state = DevCcdAcquiring
        elif acq_status == AcqReady:
            self.state = DevCcdReady
        else:
            msg = 'Acquisition error: %s' % (ct_status)
            end = index(msg, ', ImageCounters')
            msg = msg[:end] + '>'
            self.m_acq.resetStatus()
            raise Exception, msg
        deb.Return('Device state: 0x%08x (%d)' % (self.state, self.state))
        return self.state

    @TACO_SERVER_FUNCT
    def getStatus(self):
        state = self.getState()
        dev_status = self.StateDesc[state]
        ccd_status = self.m_acq.getCcdStatus()
        status = '%s (CCD Status: 0x%02X)' % (dev_status, ccd_status)
        deb.Return('Dev status: %s' % status)
        return status

    @TACO_SERVER_FUNCT
    def getFrameDim(self, max_dim=False):
        return self.m_acq.getFrameDim(max_dim)
    
    @TACO_SERVER_FUNCT
    def getType(self):
        model = self.m_acq.getCameraModel()
        type_nb = ((model.getAdcBits() == 16) and 2016) or 2014
        deb.Return('Getting type: %s' % type_nb)
        return type_nb

    @TACO_SERVER_FUNCT
    def getLstErrMsg(self):
        err_msg = ''
        deb.Return('Getting last err. msg: %s' % err_msg)
        return err_msg

    @TACO_SERVER_FUNCT
    def setTrigger(self, ext_trig):
        deb.Param('Setting trigger: %s' % ext_trig)
        exp_time = self.getExpTime()
        if ext_trig == 0:
            trig_mode = IntTrig
        elif ext_trig == 1:
            trig_mode = ((exp_time == 0) and ExtGate) or ExtTrigSingle
        elif ext_trig == 2:
            trig_mode = ExtTrigMult
        else:
            raise Exception, 'Invalid ext. trig: %s' % ext_trig
        self.m_acq.setTriggerMode(trig_mode)
    
    @TACO_SERVER_FUNCT
    def getTrigger(self):
        trig_mode = self.m_acq.getTriggerMode()
        if trig_mode == IntTrig:
            ext_trig = 0
        elif trig_mode in [ExtTrigSingle, ExtGate]:
            ext_trig = 1
        elif trig_mode == ExtTrigMult:
            ext_trig = 2
        else:
            raise Exception, 'Invalid trigger mode: %s' % trig_mode
        deb.Return('Getting trigger: %s' % ext_trig)
        return ext_trig
    
    @TACO_SERVER_FUNCT
    def setNbFrames(self, nb_frames):
        self.m_acq.setNbFrames(nb_frames)
        if self.m_acq.getStripeConcat():
            nb_concat_frames = nb_frames or self.LiveNbConcatFrames
            self.m_acq.setNbConcatFrames(nb_concat_frames)
    
    @TACO_SERVER_FUNCT
    def getNbFrames(self):
        return self.m_acq.getNbFrames()
    
    @TACO_SERVER_FUNCT
    def setExpTime(self, exp_time):
        deb.Param('Setting exp. time: %s' % exp_time)
        trig_mode = self.m_acq.getTriggerMode()
        if exp_time == 0:
            if trig_mode == IntTrig:
                raise Exception, 'Invalid NULL exp_time: trigger is internal'
            self.m_acq.setTriggerMode(ExtGate)
        else:
            if trig_mode == ExtGate:
                self.m_acq.setTriggerMode(ExtTrigSingle)
            self.m_acq.setExpTime(exp_time)
    
    @TACO_SERVER_FUNCT
    def getExpTime(self):
        trig_mode = self.m_acq.getTriggerMode()
        if trig_mode == ExtGate:
            exp_time = 0
        else:
            exp_time = self.m_acq.getExpTime()
        deb.Return('Getting Exp. time: %s' % exp_time)
        return exp_time

    @TACO_SERVER_FUNCT
    def setBin(self, bin):
        # SPEC format Y,X -> incompat. with getBin ...
        bin = Bin(bin[1], bin[0])
        self.m_acq.setBin(bin)

    @TACO_SERVER_FUNCT
    def getBin(self):
        bin = self.m_acq.getBin()
        return [bin.getX(), bin.getY()]

    @TACO_SERVER_FUNCT
    def setRoi(self, roi):
        roi = Roi(Point(roi[0], roi[1]), Point(roi[2], roi[3]))
        self.m_acq.setRoi(roi)

    @TACO_SERVER_FUNCT
    def getRoi(self):
        roi = self.m_acq.getRoi()
        tl = roi.getTopLeft()
        br = roi.getBottomRight()
        return [tl.x, tl.y, br.x, br.y]
            
    @TACO_SERVER_FUNCT
    def setFilePar(self, par_arr):
        deb.Param('Setting file pars: %s' % par_arr)
        stream_idx, active = '0', '1'
        self.setExtFilePar([stream_idx, active] + par_arr)

    @TACO_SERVER_FUNCT
    def getFilePar(self):
        stream_idx = '0'
        par_arr = self.getExtFilePar(stream_idx)[2:]
        deb.Return('Getting file pars: %s' % par_arr)
        return par_arr

    @TACO_SERVER_FUNCT
    def setExtFilePar(self, par_arr):
        stream_idx, active = map(int, par_arr[0:2])
        par_arr = par_arr[2:]
        deb.Param('Setting stream %d ext. pars: act=%s, %s' %
                  (stream_idx, active, par_arr))
        pars = self.m_acq.getFileStreamPar(stream_idx)
        pars.directory  = par_arr[0]
        pars.prefix     = par_arr[1]
        pars.suffix     = par_arr[2]
        pars.nextNumber = int(par_arr[3])
        index_format    = par_arr[4]
        if par_arr[5] in ['y', 'yes']:
            pars.overwritePolicy = CtSaving.Overwrite
        else:
            pars.overwritePolicy = CtSaving.Abort
        if pars.suffix.lower()[-4:] == '.edf':
            pars.fileFormat = CtSaving.EDF
        else:
            pars.fileFormat = CtSaving.RAW
        self.m_acq.setFileStreamAct(active, stream_idx)
        self.m_acq.setFileStreamPar(pars, stream_idx)

    @TACO_SERVER_FUNCT
    def getExtFilePar(self, stream_idx_str):
        stream_idx = int(stream_idx_str)
        active = self.m_acq.getFileStreamAct(stream_idx)
        pars = self.m_acq.getFileStreamPar(stream_idx)
        overwrite = (pars.overwritePolicy == CtSaving.Overwrite)
        overwrite = (overwrite and 'yes') or 'no'
        arr = [stream_idx, int(active), pars.directory, pars.prefix,
               pars.suffix, pars.nextNumber, pars.fileFormat, overwrite]
        par_arr = map(str, arr)
        deb.Return('Stream %d ext. pars: act=%s, %s' %
                   (stream_idx, active, par_arr[2:]))
        return par_arr

    @TACO_SERVER_FUNCT
    def setFileHeader(self, header_str):
        deb.Param('Setting file header: %s' % header_str)
        header_map = {}
        for line in header_str.split('\n'):
            token = line.split('=')
            key = token[0].strip()
            if not key:
                continue
            val = string.join(token[1:], '=').strip()
            if val[-1] == ';':
                val = val[:-1].strip()
            header_map[key] = val
        self.m_acq.setCommonFileHeader(header_map)
        
    @TACO_SERVER_FUNCT
    def writeFile(self, frame_nb):
        self.m_acq.writeFile(frame_nb, 1)
        
    @TACO_SERVER_FUNCT
    def writeConcatFramesFile(self):
        nb_frames = self.m_acq.getNbConcatFrames()
        self.m_acq.writeFile(0, nb_frames)
        
    @TACO_SERVER_FUNCT
    def setChannel(self, input_chan):
        self.m_acq.setInputChan(input_chan)
    
    @TACO_SERVER_FUNCT
    def getChannel(self):
        return self.m_acq.getInputChan()
        
    @TACO_SERVER_FUNCT
    def setMode(self, mode):
        deb.Param('Setting mode: %s (0x%x)' % (mode, mode))
        stripe_concat = (mode & self.StripeConcat) != 0
        self.m_acq.setStripeConcat(stripe_concat)
        live_display = (mode & self.LiveDisplay) != 0
        self.m_acq.setLiveDisplay(live_display)
        auto_save = (mode & self.AutoSave) != 0
        self.m_acq.setAutosave(auto_save)
        self.m_get_acq_frames = (mode & self.GetAcqFrames) != 0
        e2v_corr_act = (mode & self.DisableE2VCorr) == 0
        self.m_acq.setE2VCorrectionActive(e2v_corr_act)
        
    @TACO_SERVER_FUNCT
    def getMode(self):
        mode = 0
        if self.m_acq.getStripeConcat():
            mode |= self.StripeConcat
        if self.m_acq.getLiveDisplay():
            mode |= self.LiveDisplay
        if self.m_acq.getAutosave():
            mode |= self.AutoSave
        if self.m_get_acq_frames:
            mode |= self.GetAcqFrames
        if not self.m_acq.getE2VCorrectionActive():
            mode |= self.DisableE2VCorr
        deb.Return('Getting mode: %s (0x%x)' % (mode, mode))
        return mode

    @TACO_SERVER_FUNCT
    def setHwPar(self, hw_par_str):
        hw_par = map(int, string.split(hw_par_str))
        deb.Param('Setting hw par: %s' % hw_par)
        kin_win_size, kin_line_beg, kin_stripes = self.getKinPars()
        flip_mode, kin_line_beg, kin_stripes, d0, roi_mode_int = hw_par
        flip = Flip(flip_mode >> 1, flip_mode & 1)
        self.m_acq.setFlip(flip)
        roi_mode = Frelon.RoiMode(roi_mode_int)
        self.m_acq.setRoiMode(roi_mode)
        if roi_mode == Frelon.Kinetic:
            max_frame_dim = self.getFrameDim(max_dim=True)
            frame_height = max_frame_dim.getSize().getHeight()
            if kin_line_beg + kin_win_size > frame_height:
                kin_win_size = frame_height - kin_line_beg
                bin_y = self.m_acq.getBin().getY()
                kin_win_size = (kin_win_size / bin_y) * bin_y
                deb.Trace('Re-adjusting kin_win_size to %d to fit chip' %
                          kin_win_size)
            self.setKinPars(kin_win_size, kin_line_beg, kin_stripes)
        else:
            deb.Warning('Ingoring Kinetic parameters')
        
    @TACO_SERVER_FUNCT
    def getHwPar(self):
        flip = self.m_acq.getFlip()
        flip_mode = flip.x << 1 | flip.y
        roi_mode = self.m_acq.getRoiMode()
        kin_win_size, kin_line_beg, kin_stripes = self.getKinPars()
        hw_par = [flip_mode, kin_line_beg, kin_stripes, 0, roi_mode]
        deb.Return('Getting hw par: %s' % hw_par)
        hw_par_str = string.join(map(str, hw_par))
        return hw_par_str

    @TACO_SERVER_FUNCT
    def setKinetics(self, kinetics):
        deb.Param('Setting the profile: %s' % kinetics)
        if kinetics == 0:
            ftm = Frelon.FFM
        elif kinetics == 3:
            ftm = Frelon.FTM
        else:
            raise Exception, 'Invalid profile value: %s' % kinetics
        self.m_acq.setFrameTransferMode(ftm)
        
    @TACO_SERVER_FUNCT
    def getKinetics(self):
        ftm = self.m_acq.getFrameTransferMode()
        if ftm == Frelon.FTM:
            kinetics = 3
        else:
            kinetics = 0
        deb.Return('Getting the profile: %s' % kinetics)
        return kinetics
    
    @TACO_SERVER_FUNCT
    def setKinWinSize(self, kin_win_size):
        deb.Param('Setting the kinetics window size: %s' % kin_win_size)
        prev_win_size, kin_line_beg, kin_stripes = self.getKinPars()
        self.setKinPars(kin_win_size, kin_line_beg, kin_stripes)
    
    @TACO_SERVER_FUNCT
    def getKinWinSize(self):
        kin_win_size, kin_line_beg, kin_stripes = self.getKinPars()
        deb.Return('Getting the kinetics window size: %s' % kin_win_size)
        return kin_win_size

    @TACO_SERVER_FUNCT
    def setKinPars(self, kin_win_size, kin_line_beg, kin_stripes):
        deb.Param('Setting kin pars: ' +
                  'kin_win_size=%s, kin_line_beg=%s, kin_stripes=%s' % \
                  (kin_win_size, kin_line_beg, kin_stripes))
        if kin_stripes > 1:
            deb.Warning('Ignoring kin_stripes=%d' % kin_stripes)
            
        bin = self.m_acq.getBin()
        if kin_win_size % bin.getY() != 0:
            msg = 'Invalid kinetics window size (%d): ' % kin_win_size + \
                  'must be multiple of vert. bin (%d)' % bin.getY()
            raise Exception, msg

        roi = self.m_acq.getRoi()
        roi = roi.getUnbinned(bin)
        tl = Point(roi.getTopLeft().x, kin_line_beg)
        size = Size(roi.getSize().getWidth(), kin_win_size)
        roi = Roi(tl, size)
        roi = roi.getBinned(bin)
        self.m_acq.setRoi(roi)

        self.m_acq.setRoiLineBegin(kin_line_beg)
        
    @TACO_SERVER_FUNCT
    def getKinPars(self):
        bin = self.m_acq.getBin()
        roi = self.m_acq.getRoi()
        roi = roi.getUnbinned(bin)
        kin_win_size = roi.getSize().getHeight()
        kin_line_beg = self.m_acq.getRoiLineBegin()
        kin_stripes = 1
        deb.Return('Getting kin pars: ' +
                   'kin_win_size=%s, kin_line_beg=%s, kin_stripes=%s' % \
                   (kin_win_size, kin_line_beg, kin_stripes))
        return kin_win_size, kin_line_beg, kin_stripes

    @TACO_SERVER_FUNCT
    def startAcq(self):
        self.m_acq.startAcq()
                
    @TACO_SERVER_FUNCT
    def stopAcq(self):
        self.m_acq.stopAcq()
    
    @TACO_SERVER_FUNCT
    def readFrame(self, frame_data):
        frame_nb, frame_size = frame_data
        deb.Param('frame_nb=%s, frame_size=%s' % (frame_nb, frame_size))
        frame_dim = self.m_acq.getFrameDim()
        if frame_size != frame_dim.getMemSize():
            raise ValueError, ('Client expects %d bytes, frame has %d' % \
                               (frame_size, frame_dim.getMemSize()))
        s = self.m_acq.readFrames(frame_nb, 1)
        if len(s) != frame_size:
            raise ValueError, ('Client expects %d bytes, data str has %d' % \
                               (frame_size, len(s)))
        return s
    
    @TACO_SERVER_FUNCT
    def readConcatFrames(self, frame_size):
        frame_dim = self.getFrameDim()
        nb_frames = frame_size / frame_dim.getMemSize()
        s = self.m_acq.readFrames(0, nb_frames)
        if len(s) != frame_size:
            raise ValueError, ('Client expects %d bytes, data str has %d' % \
                               (frame_size, len(s)))
        return s

    @TACO_SERVER_FUNCT
    def startLive(self):
        self.m_acq.startLive()
        
    @TACO_SERVER_FUNCT
    def getCurrent(self):
        ct_status = self.m_acq.getStatus()
        img_counters = ct_status.ImageCounters
        if self.m_acq.getAutosave() and not self.m_get_acq_frames:
            last_frame_nb = img_counters.LastImageSaved
        else:
            last_frame_nb = img_counters.LastImageAcquired
        nb_frames = last_frame_nb + 1
        deb.Return('Nb of frames: %s' % nb_frames)
        return nb_frames

    @TACO_SERVER_FUNCT
    def execCommand(self, cmd):
        return self.m_acq.execFrelonSerialCmd(cmd)

    @TACO_SERVER_FUNCT
    def getChanges(self):
        changes = 0
        deb.Trace('Getting changes: %s' % changes)
        return changes

    @TACO_SERVER_FUNCT
    def readCcdParams(self):
        exp_time = self.getExpTime()
        threshold = 0
        calib_intensity = -1
        max_frame_dim = self.m_acq.getFrameDim(max_dim=True)
        roi = self.getRoi()
        is_live = -1

        ccd_params = [exp_time,
                      threshold,
                      calib_intensity,
                      max_frame_dim.getSize().getWidth(),
                      max_frame_dim.getSize().getHeight(),
                      roi[0], roi[1], roi[2], roi[3],
                      is_live]
        
        beam_params = self.readBeamParams()
        if exp_time == 0:
            beam_params[19] = 0
        ccd_params += beam_params
        deb.Return('Getting CCD params: %s' % ccd_params)
        return ccd_params

    @TACO_SERVER_FUNCT
    def readBeamParams(self):
        return self.m_acq.readBeamParams()


class FrelonServer(CcdServer):

    DEB_CLASS(DebModApplication, "FrelonServer")
    
    @DEB_MEMBER_FUNCT
    def __init__(self, bin_name, pers_name):
        CcdServer.__init__(self, bin_name, pers_name)

        dev_name_list = self.getDevNameList()
        dev_model_list = []

        for dev_name in dev_name_list:
            dev = FrelonTacoAcq(dev_name)
            self.addDev(dev)

            model_str = dev.m_acq.getCameraModelStr()
            dev_model_list.append(model_str)
            
        deb.Always("Using following cameras:")
        for dev_name, model_str in zip(dev_name_list, dev_model_list):
            deb.Always("  %s - %s" % (dev_name, model_str))
            
        self.startup()
        
