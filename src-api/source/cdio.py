#================================================================
# cdio.py
# module file for CONTEC Digital I/O device
#                                                CONTEC.Co., Ltd.
#================================================================
import ctypes
import ctypes.wintypes

cdio_dll = ctypes.windll.LoadLibrary('cdio.dll')


#----------------------------------------
# Types for callback function.
#----------------------------------------
PDIO_INT_CALLBACK = ctypes.WINFUNCTYPE(None,
                                       ctypes.c_short,  ctypes.wintypes.WPARAM,
                                       ctypes.wintypes.LPARAM, ctypes.c_void_p)
PDIO_TRG_CALLBACK = ctypes.WINFUNCTYPE(None,
                                       ctypes.c_short,  ctypes.wintypes.WPARAM,
                                       ctypes.wintypes.LPARAM, ctypes.c_void_p)
PDIO_DM_COUNT_CALLBACK = ctypes.WINFUNCTYPE(None,
                                            ctypes.c_short,  ctypes.wintypes.WPARAM,
                                            ctypes.wintypes.LPARAM, ctypes.c_void_p)
PDIO_DM_STOP_CALLBACK = ctypes.WINFUNCTYPE(None,
                                           ctypes.c_short,  ctypes.wintypes.WPARAM,
                                           ctypes.wintypes.LPARAM, ctypes.c_void_p)


#----------------------------------------
# Prototype definition
#----------------------------------------
#----------------------------------------
# Common function
#----------------------------------------
# C Prototype: long WINAPI DioInit(char *DeviceName, short *Id);
DioInit = cdio_dll.DioInit
DioInit.restype = ctypes.c_long
DioInit.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_short)]

# C Prototype: long WINAPI DioExit(short Id);
DioExit = cdio_dll.DioExit
DioExit.restype = ctypes.c_long
DioExit.argtypes = [ctypes.c_short]

# C Prototype: long WINAPI DioResetDevice(short Id);
DioResetDevice = cdio_dll.DioResetDevice
DioResetDevice.restype = ctypes.c_long
DioResetDevice.argtypes = [ctypes.c_short]

# C Prototype: long WINAPI DioGetErrorString(long ErrorCode , char *ErrorString);
DioGetErrorString = cdio_dll.DioGetErrorString
DioGetErrorString.restype = ctypes.c_long
DioGetErrorString.argtypes = [ctypes.c_long, ctypes.c_char_p]

# C Prototype: long WINAPI DioGetNetCommunicationInfo(short Id, short InfoType, long *InfoData);
DioGetNetCommunicationInfo = cdio_dll.DioGetNetCommunicationInfo
DioGetNetCommunicationInfo.restype = ctypes.c_long
DioGetNetCommunicationInfo.argtypes = [ctypes.c_short, ctypes.c_short, ctypes.POINTER(ctypes.c_long)]

#----------------------------------------
# Digital filter function
#----------------------------------------
# C Prototype: long WINAPI DioSetDigitalFilter(short Id, short FilterValue);
DioSetDigitalFilter = cdio_dll.DioSetDigitalFilter
DioSetDigitalFilter.restype = ctypes.c_long
DioSetDigitalFilter.argtypes = [ctypes.c_short, ctypes.c_short]

# C Prototype: long WINAPI DioGetDigitalFilter(short Id, short *FilterValue);
DioGetDigitalFilter = cdio_dll.DioGetDigitalFilter
DioGetDigitalFilter.restype = ctypes.c_long
DioGetDigitalFilter.argtypes = [ctypes.c_short, ctypes.POINTER(ctypes.c_short)]

#----------------------------------------
# I/O Direction function
#----------------------------------------
# C Prototype: long WINAPI DioSetIoDirection(short Id, DWORD Dir);
DioSetIoDirection = cdio_dll.DioSetIoDirection
DioSetIoDirection.restype = ctypes.c_long
DioSetIoDirection.argtypes = [ctypes.c_short, ctypes.c_ulong]

# C Prototype: long WINAPI DioGetIoDirection(short Id, DWORD *Dir);
DioGetIoDirection = cdio_dll.DioGetIoDirection
DioGetIoDirection.restype = ctypes.c_long
DioGetIoDirection.argtypes = [ctypes.c_short, ctypes.POINTER(ctypes.c_ulong)]

# C Prototype: long WINAPI DioSetIoDirectionEx(short Id, DWORD dwDir);
DioSetIoDirectionEx = cdio_dll.DioSetIoDirectionEx
DioSetIoDirectionEx.restype = ctypes.c_long
DioSetIoDirectionEx.argtypes = [ctypes.c_short, ctypes.c_ulong]

# C Prototype: long WINAPI DioGetIoDirectionEx(short Id, DWORD *dwDir);
DioGetIoDirectionEx = cdio_dll.DioGetIoDirectionEx
DioGetIoDirectionEx.restype = ctypes.c_long
DioGetIoDirectionEx.argtypes = [ctypes.c_short, ctypes.POINTER(ctypes.c_ulong)]

# C Prototype: long WINAPI DioSet8255Mode(short Id, short ChipNo, short CtrlWord);
DioSet8255Mode = cdio_dll.DioSet8255Mode
DioSet8255Mode.restype = ctypes.c_long
DioSet8255Mode.argtypes = [ctypes.c_short, ctypes.c_short, ctypes.c_short]

# C Prototype: long WINAPI DioGet8255Mode(short Id, short ChipNo, short *CtrlWord);
DioGet8255Mode = cdio_dll.DioGet8255Mode
DioGet8255Mode.restype = ctypes.c_long
DioGet8255Mode.argtypes = [ctypes.c_short, ctypes.c_short, ctypes.POINTER(ctypes.c_short)]

#----------------------------------------
# Simple I/O function
#----------------------------------------
# C Prototype: long WINAPI DioInpByte(short Id, short PortNo, BYTE *Data);
DioInpByte = cdio_dll.DioInpByte
DioInpByte.restype = ctypes.c_long
DioInpByte.argtypes = [ctypes.c_short, ctypes.c_short, ctypes.POINTER(ctypes.c_ubyte)]

# C Prototype: long WINAPI DioInpBit(short Id, short BitNo, BYTE *Data);
DioInpBit = cdio_dll.DioInpBit
DioInpBit.restype = ctypes.c_long
DioInpBit.argtypes = [ctypes.c_short, ctypes.c_short, ctypes.POINTER(ctypes.c_ubyte)]

# C Prototype: long WINAPI DioInpByteSR(short Id, short PortNo, unsigned char *Data, unsigned short *Timestamp, BYTE Mode);
DioInpByteSR = cdio_dll.DioInpByteSR
DioInpByteSR.restype = ctypes.c_long
DioInpByteSR.argtypes = [ctypes.c_short, ctypes.c_short, ctypes.POINTER(ctypes.c_ubyte),
                         ctypes.POINTER(ctypes.c_ushort), ctypes.c_ubyte]

# C Prototype: long WINAPI DioInpBitSR(short Id, short BitNo, unsigned char *Data, unsigned short *Timestamp, BYTE Mode);
DioInpBitSR = cdio_dll.DioInpBitSR
DioInpBitSR.restype = ctypes.c_long
DioInpBitSR.argtypes = [ctypes.c_short, ctypes.c_short, ctypes.POINTER(ctypes.c_ubyte),
                        ctypes.POINTER(ctypes.c_ushort), ctypes.c_ubyte]

# C Prototype: long WINAPI DioOutByte(short Id, short PortNo, BYTE Data);
DioOutByte = cdio_dll.DioOutByte
DioOutByte.restype = ctypes.c_long
DioOutByte.argtypes = [ctypes.c_short, ctypes.c_short, ctypes.c_ubyte]

# C Prototype: long WINAPI DioOutBit(short Id, short BitNo, BYTE Data);
DioOutBit = cdio_dll.DioOutBit
DioOutBit.restype = ctypes.c_long
DioOutBit.argtypes = [ctypes.c_short, ctypes.c_short, ctypes.c_ubyte]

# C Prototype: long WINAPI DioEchoBackByte(short Id, short PortNo, BYTE *Data);
DioEchoBackByte = cdio_dll.DioEchoBackByte
DioEchoBackByte.restype = ctypes.c_long
DioEchoBackByte.argtypes = [ctypes.c_short, ctypes.c_short, ctypes.POINTER(ctypes.c_ubyte)]

# C Prototype: long WINAPI DioEchoBackBit(short Id, short BitNo, BYTE *Data);
DioEchoBackBit = cdio_dll.DioEchoBackBit
DioEchoBackBit.restype = ctypes.c_long
DioEchoBackBit.argtypes = [ctypes.c_short, ctypes.c_short, ctypes.POINTER(ctypes.c_ubyte)]

#----------------------------------------
# Multiple I/O function
#----------------------------------------
# C Prototype: long WINAPI DioInpMultiByte(short Id, short *PortNo, short PortNum, BYTE *Data);
DioInpMultiByte = cdio_dll.DioInpMultiByte
DioInpMultiByte.restype = ctypes.c_long
DioInpMultiByte.argtypes = [ctypes.c_short, ctypes.POINTER(ctypes.c_short), ctypes.c_short,
                            ctypes.POINTER(ctypes.c_ubyte)]

# C Prototype: long WINAPI DioInpMultiBit(short Id, short *BitNo, short BitNum, BYTE *Data);
DioInpMultiBit = cdio_dll.DioInpMultiBit
DioInpMultiBit.restype = ctypes.c_long
DioInpMultiBit.argtypes = [ctypes.c_short, ctypes.POINTER(ctypes.c_short), ctypes.c_short,
                           ctypes.POINTER(ctypes.c_ubyte)]

# C Prototype: long WINAPI DioInpMultiByteSR(short Id, short *PortNo, short PortNum, unsigned char *Data, unsigned short *Timestamp, unsigned char Mode);
DioInpMultiByteSR = cdio_dll.DioInpMultiByteSR
DioInpMultiByteSR.restype = ctypes.c_long
DioInpMultiByteSR.argtypes = [ctypes.c_short, ctypes.POINTER(ctypes.c_short), ctypes.c_short,
                              ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(ctypes.c_ushort),
                              ctypes.c_ubyte]

# C Prototype: long WINAPI DioInpMultiBitSR(short Id, short *BitNo, short BitNum, unsigned char *Data, unsigned short *Timestamp, unsigned char Mode);
DioInpMultiBitSR = cdio_dll.DioInpMultiBitSR
DioInpMultiBitSR.restype = ctypes.c_long
DioInpMultiBitSR.argtypes = [ctypes.c_short, ctypes.POINTER(ctypes.c_short), ctypes.c_short,
                             ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(ctypes.c_ushort),
                             ctypes.c_ubyte]

# C Prototype: long WINAPI DioOutMultiByte(short Id, short *PortNo, short PortNum, BYTE *Data);
DioOutMultiByte = cdio_dll.DioOutMultiByte
DioOutMultiByte.restype = ctypes.c_long
DioOutMultiByte.argtypes = [ctypes.c_short, ctypes.POINTER(ctypes.c_short), ctypes.c_short,
                            ctypes.POINTER(ctypes.c_ubyte)]

# C Prototype: long WINAPI DioOutMultiBit(short Id, short *BitNo, short BitNum, BYTE *Data);
DioOutMultiBit = cdio_dll.DioOutMultiBit
DioOutMultiBit.restype = ctypes.c_long
DioOutMultiBit.argtypes = [ctypes.c_short, ctypes.POINTER(ctypes.c_short), ctypes.c_short,
                           ctypes.POINTER(ctypes.c_ubyte)]

# C Prototype: long WINAPI DioEchoBackMultiByte(short Id, short *PortNo, short PortNum, BYTE *Data);
DioEchoBackMultiByte = cdio_dll.DioEchoBackMultiByte
DioEchoBackMultiByte.restype = ctypes.c_long
DioEchoBackMultiByte.argtypes = [ctypes.c_short, ctypes.POINTER(ctypes.c_short), ctypes.c_short,
                                 ctypes.POINTER(ctypes.c_ubyte)]

# C Prototype: long WINAPI DioEchoBackMultiBit(short Id, short *BitNo, short BitNum, BYTE *Data);
DioEchoBackMultiBit = cdio_dll.DioEchoBackMultiBit
DioEchoBackMultiBit.restype = ctypes.c_long
DioEchoBackMultiBit.argtypes = [ctypes.c_short, ctypes.POINTER(ctypes.c_short), ctypes.c_short,
                                ctypes.POINTER(ctypes.c_ubyte)]

#----------------------------------------
# Interrupt function
#----------------------------------------
# C Prototype: long WINAPI DioNotifyInterrupt(short Id, short BitNo, short Logic, HANDLE hWnd);
DioNotifyInterrupt = cdio_dll.DioNotifyInterrupt
DioNotifyInterrupt.restype = ctypes.c_long
DioNotifyInterrupt.argtypes = [ctypes.c_short, ctypes.c_short, ctypes.c_short, ctypes.wintypes.HANDLE]

# C Prototype: long WINAPI DioSetInterruptCallBackProc(short Id, PDIO_INT_CALLBACK CallBackProc, void *Param);
DioSetInterruptCallBackProc = cdio_dll.DioSetInterruptCallBackProc
DioSetInterruptCallBackProc.restype = ctypes.c_long
DioSetInterruptCallBackProc.argtypes = [ctypes.c_short, PDIO_INT_CALLBACK, ctypes.c_void_p]

#----------------------------------------
# Trigger function
#----------------------------------------
# C Prototype: long WINAPI DioNotifyTrg(short Id, short TrgBit, short TrgKind, long Tim, HANDLE hWnd);
DioNotifyTrg = cdio_dll.DioNotifyTrg
DioNotifyTrg.restype = ctypes.c_long
DioNotifyTrg.argtypes = [ctypes.c_short, ctypes.c_short, ctypes.c_short, ctypes.c_long, ctypes.wintypes.HANDLE]

# C Prototype: long WINAPI DioStopNotifyTrg(short Id, short TrgBit);
DioStopNotifyTrg = cdio_dll.DioStopNotifyTrg
DioStopNotifyTrg.restype = ctypes.c_long
DioStopNotifyTrg.argtypes = [ctypes.c_short, ctypes.c_short]

# C Prototype: long WINAPI DioSetTrgCallBackProc(short Id, PDIO_TRG_CALLBACK CallBackProc, void *Param);
DioSetTrgCallBackProc = cdio_dll.DioSetTrgCallBackProc
DioSetTrgCallBackProc.restype = ctypes.c_long
DioSetTrgCallBackProc.argtypes = [ctypes.c_short, PDIO_TRG_CALLBACK, ctypes.c_void_p]

#----------------------------------------
# Information function
#----------------------------------------
# C Prototype: long WINAPI DioGetDeviceInfo(char *Device, short InfoType, void *Param1, void *Param2, void *Param3);
DioGetDeviceInfo = cdio_dll.DioGetDeviceInfo
DioGetDeviceInfo.restype = ctypes.c_long
DioGetDeviceInfo.argtypes = [ctypes.c_char_p, ctypes.c_short, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]

# C Prototype: long WINAPI DioQueryDeviceName(short Index, char *DeviceName, char *Device);
DioQueryDeviceName = cdio_dll.DioQueryDeviceName
DioQueryDeviceName.restype = ctypes.c_long
DioQueryDeviceName.argtypes = [ctypes.c_short, ctypes.c_char_p, ctypes.c_char_p]

# C Prototype: long WINAPI DioGetDeviceType(char *Device, short *DeviceType);
DioGetDeviceType = cdio_dll.DioGetDeviceType
DioGetDeviceType.restype = ctypes.c_long
DioGetDeviceType.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_short)]

# C Prototype: long WINAPI DioGetMaxPorts(short Id, short *InPortNum, short *OutPortNum);
DioGetMaxPorts = cdio_dll.DioGetMaxPorts
DioGetMaxPorts.restype = ctypes.c_long
DioGetMaxPorts.argtypes = [ctypes.c_short, ctypes.POINTER(ctypes.c_short), ctypes.POINTER(ctypes.c_short)]

# C Prototype: long WINAPI DioGetMaxCountChannels(short Id, short *ChannelNum);
DioGetMaxCountChannels = cdio_dll.DioGetMaxCountChannels
DioGetMaxCountChannels.restype = ctypes.c_long
DioGetMaxCountChannels.argtypes = [ctypes.c_short, ctypes.POINTER(ctypes.c_short)]

#----------------------------------------
# Counter function
#----------------------------------------
# C Prototype: long WINAPI DioSetCountEdge(short Id, short *ChNo, short ChNum, short *CountEdge);
DioSetCountEdge = cdio_dll.DioSetCountEdge
DioSetCountEdge.restype = ctypes.c_long
DioSetCountEdge.argtypes = [ctypes.c_short, ctypes.POINTER(ctypes.c_short), ctypes.c_short,
                            ctypes.POINTER(ctypes.c_short)]

# C Prototype: long WINAPI DioGetCountEdge(short Id, short *ChNo, short ChNum, short *CountEdge);
DioGetCountEdge = cdio_dll.DioGetCountEdge
DioGetCountEdge.restype = ctypes.c_long
DioGetCountEdge.argtypes = [ctypes.c_short, ctypes.POINTER(ctypes.c_short), ctypes.c_short,
                            ctypes.POINTER(ctypes.c_short)]

# C Prototype: long WINAPI DioSetCountMatchValue(short Id, short *ChNo, short ChNum, short *CompareRegNo, unsigned long *CompareCount);
DioSetCountMatchValue = cdio_dll.DioSetCountMatchValue
DioSetCountMatchValue.restype = ctypes.c_long
DioSetCountMatchValue.argtypes = [ctypes.c_short, ctypes.POINTER(ctypes.c_short), ctypes.c_short,
                                  ctypes.POINTER(ctypes.c_short), ctypes.POINTER(ctypes.c_ulong)]

# C Prototype: long WINAPI DioStartCount(short Id, short *ChNo, short ChNum);
DioStartCount = cdio_dll.DioStartCount
DioStartCount.restype = ctypes.c_long
DioStartCount.argtypes = [ctypes.c_short, ctypes.POINTER(ctypes.c_short), ctypes.c_short]

# C Prototype: long WINAPI DioStopCount(short Id, short *ChNo, short ChNum);
DioStopCount = cdio_dll.DioStopCount
DioStopCount.restype = ctypes.c_long
DioStopCount.argtypes = [ctypes.c_short, ctypes.POINTER(ctypes.c_short), ctypes.c_short]

# C Prototype: long WINAPI DioGetCountStatus(short Id, short *ChNo, short ChNum, unsigned long *CountStatus);
DioGetCountStatus = cdio_dll.DioGetCountStatus
DioGetCountStatus.restype = ctypes.c_long
DioGetCountStatus.argtypes = [ctypes.c_short, ctypes.POINTER(ctypes.c_short), ctypes.c_short,
                              ctypes.POINTER(ctypes.c_ulong)]

# C Prototype: long WINAPI DioCountPreset(short Id, short *ChNo, short ChNum, unsigned long *PresetCount);
DioCountPreset = cdio_dll.DioCountPreset
DioCountPreset.restype = ctypes.c_long
DioCountPreset.argtypes = [ctypes.c_short, ctypes.POINTER(ctypes.c_short), ctypes.c_short,
                           ctypes.POINTER(ctypes.c_ulong)]

# C Prototype: long WINAPI DioReadCount(short Id, short *ChNo, short ChNum, unsigned long *Count);
DioReadCount = cdio_dll.DioReadCount
DioReadCount.restype = ctypes.c_long
DioReadCount.argtypes = [ctypes.c_short, ctypes.POINTER(ctypes.c_short), ctypes.c_short, ctypes.POINTER(ctypes.c_ulong)]

# C Prototype: long WINAPI DioReadCountSR(short Id, short *ChNo, short ChNum, unsigned long *Count, unsigned short * Timestamp, BYTE Mode);
DioReadCountSR = cdio_dll.DioReadCountSR
DioReadCountSR.restype = ctypes.c_long
DioReadCountSR.argtypes = [ctypes.c_short, ctypes.POINTER(ctypes.c_short), ctypes.c_short, ctypes.POINTER(ctypes.c_ulong), 
                           ctypes.POINTER(ctypes.c_ushort), ctypes.c_ubyte]

#----------------------------------------
# DM function
#----------------------------------------
# C Prototype: long WINAPI DioDmSetDirection(short Id, short Direction);
DioDmSetDirection = cdio_dll.DioDmSetDirection
DioDmSetDirection.restype = ctypes.c_long
DioDmSetDirection.argtypes = [ctypes.c_short, ctypes.c_short]

# C Prototype: long WINAPI DioDmGetDirection(short Id, short *Direction);
DioDmGetDirection = cdio_dll.DioDmGetDirection
DioDmGetDirection.restype = ctypes.c_long
DioDmGetDirection.argtypes = [ctypes.c_short, ctypes.POINTER(ctypes.c_short)]

# C Prototype: long WINAPI DioDmSetStandAlone(short Id);
DioDmSetStandAlone = cdio_dll.DioDmSetStandAlone
DioDmSetStandAlone.restype = ctypes.c_long
DioDmSetStandAlone.argtypes = [ctypes.c_short]

# C Prototype: long WINAPI DioDmSetMaster(short Id, short ExtSig1, short ExtSig2, short ExtSig3, short MasterHalt, short SlaveHalt);
DioDmSetMaster = cdio_dll.DioDmSetMaster
DioDmSetMaster.restype = ctypes.c_long
DioDmSetMaster.argtypes = [ctypes.c_short, ctypes.c_short, ctypes.c_short, ctypes.c_short,
                           ctypes.c_short, ctypes.c_short]

# C Prototype: long WINAPI DioDmSetSlave(short Id, short ExtSig1, short ExtSig2, short ExtSig3, short MasterHalt, short SlaveHalt);
DioDmSetSlave = cdio_dll.DioDmSetSlave
DioDmSetSlave.restype = ctypes.c_long
DioDmSetSlave.argtypes = [ctypes.c_short, ctypes.c_short, ctypes.c_short, ctypes.c_short,
                          ctypes.c_short, ctypes.c_short]

# C Prototype: long WINAPI DioDmSetStartTrigger(short Id, short Direction, short Start);
DioDmSetStartTrigger = cdio_dll.DioDmSetStartTrigger
DioDmSetStartTrigger.restype = ctypes.c_long
DioDmSetStartTrigger.argtypes = [ctypes.c_short, ctypes.c_short, ctypes.c_short]

# C Prototype: long WINAPI DioDmSetStartPattern(short Id, unsigned long Pattern, unsigned long Mask);
DioDmSetStartPattern = cdio_dll.DioDmSetStartPattern
DioDmSetStartPattern.restype = ctypes.c_long
DioDmSetStartPattern.argtypes = [ctypes.c_short, ctypes.c_ulong, ctypes.c_ulong]

# C Prototype: long WINAPI DioDmSetClockTrigger(short Id, short Direction, short Clock);
DioDmSetClockTrigger = cdio_dll.DioDmSetClockTrigger
DioDmSetClockTrigger.restype = ctypes.c_long
DioDmSetClockTrigger.argtypes = [ctypes.c_short, ctypes.c_short, ctypes.c_short]

# C Prototype: long WINAPI DioDmSetInternalClock(short Id, short Direction, unsigned long Clock, short Unit);
DioDmSetInternalClock = cdio_dll.DioDmSetInternalClock
DioDmSetInternalClock.restype = ctypes.c_long
DioDmSetInternalClock.argtypes = [ctypes.c_short, ctypes.c_short, ctypes.c_ulong, ctypes.c_short]

# C Prototype: long WINAPI DioDmSetStopTrigger(short Id, short Direction, short Stop);
DioDmSetStopTrigger = cdio_dll.DioDmSetStopTrigger
DioDmSetStopTrigger.restype = ctypes.c_long
DioDmSetStopTrigger.argtypes = [ctypes.c_short, ctypes.c_short, ctypes.c_short]

# C Prototype: long WINAPI DioDmSetStopNumber(short Id, short Direction, unsigned long StopNumber);
DioDmSetStopNumber = cdio_dll.DioDmSetStopNumber
DioDmSetStopNumber.restype = ctypes.c_long
DioDmSetStopNumber.argtypes = [ctypes.c_short, ctypes.c_short, ctypes.c_ulong]

# C Prototype: long WINAPI DioDmFifoReset(short Id, short Reset);
DioDmFifoReset = cdio_dll.DioDmFifoReset
DioDmFifoReset.restype = ctypes.c_long
DioDmFifoReset.argtypes = [ctypes.c_short, ctypes.c_short]

# C Prototype: long WINAPI DioDmSetBuffer(short Id, short Direction, unsigned long *Buffer, unsigned long Length, short IsRing);
DioDmSetBuffer = cdio_dll.DioDmSetBuffer
DioDmSetBuffer.restype = ctypes.c_long
DioDmSetBuffer.argtypes = [ctypes.c_short, ctypes.c_short, ctypes.POINTER(ctypes.c_ulong), ctypes.c_ulong,
                           ctypes.c_short]

# C Prototype: long WINAPI DioDmSetTransferStartWait(short Id, short Time);
DioDmSetTransferStartWait = cdio_dll.DioDmSetTransferStartWait
DioDmSetTransferStartWait.restype = ctypes.c_long
DioDmSetTransferStartWait.argtypes = [ctypes.c_short, ctypes.c_short]

# C Prototype: long WINAPI DioDmTransferStart(short Id, short Direction);
DioDmTransferStart = cdio_dll.DioDmTransferStart
DioDmTransferStart.restype = ctypes.c_long
DioDmTransferStart.argtypes = [ctypes.c_short, ctypes.c_short]

# C Prototype: long WINAPI DioDmTransferStop(short Id, short Direction);
DioDmTransferStop = cdio_dll.DioDmTransferStop
DioDmTransferStop.restype = ctypes.c_long
DioDmTransferStop.argtypes = [ctypes.c_short, ctypes.c_short]

# C Prototype: long WINAPI DioDmGetStatus(short Id, short Direction, unsigned long *Status, unsigned long *Err);
DioDmGetStatus = cdio_dll.DioDmGetStatus
DioDmGetStatus.restype = ctypes.c_long
DioDmGetStatus.argtypes = [ctypes.c_short, ctypes.c_short, ctypes.POINTER(ctypes.c_ulong),
                           ctypes.POINTER(ctypes.c_ulong)]

# C Prototype: long WINAPI DioDmGetCount(short Id, short Direction, unsigned long *Count, unsigned long *Carry);
DioDmGetCount = cdio_dll.DioDmGetCount
DioDmGetCount.restype = ctypes.c_long
DioDmGetCount.argtypes = [ctypes.c_short, ctypes.c_short, ctypes.POINTER(ctypes.c_ulong),
                          ctypes.POINTER(ctypes.c_ulong)]

# C Prototype: long WINAPI DioDmGetWritePointer(short Id, short Direction, unsigned long *WritePointer, unsigned long *Count, unsigned long *Carry);
DioDmGetWritePointer = cdio_dll.DioDmGetWritePointer
DioDmGetWritePointer.restype = ctypes.c_long
DioDmGetWritePointer.argtypes = [ctypes.c_short, ctypes.c_short, ctypes.POINTER(ctypes.c_ulong),
                                 ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong)]

# C Prototype: long WINAPI DioDmSetStopEvent(short Id, short Direction, HANDLE hWnd);
DioDmSetStopEvent = cdio_dll.DioDmSetStopEvent
DioDmSetStopEvent.restype = ctypes.c_long
DioDmSetStopEvent.argtypes = [ctypes.c_short, ctypes.c_short, ctypes.wintypes.HANDLE]

# C Prototype: long WINAPI DioDmSetStopCallBackProc (short Id ,PDIO_DM_STOP_CALLBACK CallBackProc , void *Param);
DioDmSetStopCallBackProc = cdio_dll.DioDmSetStopCallBackProc
DioDmSetStopCallBackProc.restype = ctypes.c_long
DioDmSetStopCallBackProc.argtypes = [ctypes.c_short, PDIO_DM_STOP_CALLBACK, ctypes.c_void_p]

# C Prototype: long WINAPI DioDmSetCountEvent(short Id, short Direction, unsigned long Count, HANDLE hWnd);
DioDmSetCountEvent = cdio_dll.DioDmSetCountEvent
DioDmSetCountEvent.restype = ctypes.c_long
DioDmSetCountEvent.argtypes = [ctypes.c_short, ctypes.c_short, ctypes.c_ulong, ctypes.wintypes.HANDLE]

# C Prototype: long WINAPI DioDmSetCountCallBackProc(short Id ,PDIO_DM_COUNT_CALLBACK CallBackProc , void *Param);
DioDmSetCountCallBackProc = cdio_dll.DioDmSetCountCallBackProc
DioDmSetCountCallBackProc.restype = ctypes.c_long
DioDmSetCountCallBackProc.argtypes = [ctypes.c_short, PDIO_DM_COUNT_CALLBACK, ctypes.c_void_p]

#----------------------------------------
# Demo Device I/O function
#----------------------------------------
# C Prototype: long WINAPI DioSetDemoByte(short Id, short PortNo, BYTE Data);
DioSetDemoByte = cdio_dll.DioSetDemoByte
DioSetDemoByte.restype = ctypes.c_long
DioSetDemoByte.argtypes = [ctypes.c_short, ctypes.c_short, ctypes.c_ubyte]

# C Prototype: long WINAPI DioSetDemoBit(short Id, short BitNo, BYTE Data);
DioSetDemoBit = cdio_dll.DioSetDemoBit
DioSetDemoBit.restype = ctypes.c_long
DioSetDemoBit.argtypes = [ctypes.c_short, ctypes.c_short, ctypes.c_ubyte]

#----------------------------------------
# Other
#----------------------------------------
# C Prototype: long WINAPI DioResetPatternEvent(short Id, char *Data);
DioResetPatternEvent = cdio_dll.DioResetPatternEvent
DioResetPatternEvent.restype = ctypes.c_long
DioResetPatternEvent.argtypes = [ctypes.c_short, ctypes.POINTER(ctypes.c_ubyte)]

# C Prototype: long WINAPI DioGetPatternEventStatus(short Id, short *Status);
DioGetPatternEventStatus = cdio_dll.DioGetPatternEventStatus
DioGetPatternEventStatus.restype = ctypes.c_long
DioGetPatternEventStatus.argtypes = [ctypes.c_short, ctypes.POINTER(ctypes.c_short)]

#----------------------------------------
# Type definition
#----------------------------------------
DEVICE_TYPE_ISA = 0             # ISA or C bus
DEVICE_TYPE_PCI = 1             # PCI bus
DEVICE_TYPE_PCMCIA = 2          # PCMCIA
DEVICE_TYPE_USB = 3             # USB
DEVICE_TYPE_FIT = 4             # FIT
DEVICE_TYPE_CARDBUS = 5         # CardBus
DEVICE_TYPE_NET = 20            # Ethernet, Wireless etc
#----------------------------------------
# Parameters
#----------------------------------------
#----------------------------------------
# I/O(for Sample)
#----------------------------------------
DIO_MAX_ACCS_PORTS = 256
#----------------------------------------
# DioNotifyInt:Logic
#----------------------------------------
DIO_INT_NONE = 0
DIO_INT_RISE = 1
DIO_INT_FALL = 2
#----------------------------------------
# DioNotifyTrg:TrgKind
#----------------------------------------
DIO_TRG_RISE = 1
DIO_TRG_FALL = 2
#----------------------------------------
# Message
#----------------------------------------
DIOM_INTERRUPT = 0x1300
DIOM_TRIGGER = 0x1340
DIO_DMM_STOP = 0x1350
DIO_DMM_COUNT = 0x1360
#----------------------------------------
# Device Information
#----------------------------------------
IDIO_DEVICE_TYPE = 0                # device type.                              Param1:short
IDIO_NUMBER_OF_8255 = 1             # Number of 8255 chip.                      Param1:int
IDIO_IS_8255_BOARD = 2              # Is 8255 board?                            Param1:int(1:true, 0:false)
IDIO_NUMBER_OF_DI_BIT = 3           # Number of digital input bit.              Param1:short
IDIO_NUMBER_OF_DO_BIT = 4           # Number of digital outout bit.             Param1:short
IDIO_NUMBER_OF_DI_PORT = 5          # Number of digital input port.             Param1:short
IDIO_NUMBER_OF_DO_PORT = 6          # Number of digital output port.            Param1:short
IDIO_IS_POSITIVE_LOGIC = 7          # Is positive logic?                        Param1:int(1:true, 0:false)
IDIO_IS_ECHO_BACK = 8               # Can echo back output port?                Param1:int(1:true, 0:false)
IDIO_IS_DIRECTION = 9               # Can DioSetIoDirection function be used?   Param1:int(1:true, 0:false)
IDIO_IS_FILTER = 10                 # Can digital filter be used?               Param1:int(1:true, 0:false)
IDIO_NUMBER_OF_INT_BIT = 11         # Number of interrupt bit.                  Param1:short
#----------------------------------------
# Direction
#----------------------------------------
PI_32 = 1
PO_32 = 2
PIO_1616 = 3
DIODM_DIR_IN = 0x1
DIODM_DIR_OUT = 0x2
#----------------------------------------
# Start
#----------------------------------------
DIODM_START_SOFT = 1
DIODM_START_EXT_RISE = 2
DIODM_START_EXT_FALL = 3
DIODM_START_PATTERN = 4
DIODM_START_EXTSIG_1 = 5
DIODM_START_EXTSIG_2 = 6
DIODM_START_EXTSIG_3 = 7
#----------------------------------------
# Clock
#----------------------------------------
DIODM_CLK_CLOCK = 1
DIODM_CLK_EXT_TRG = 2
DIODM_CLK_HANDSHAKE = 3
DIODM_CLK_EXTSIG_1 = 4
DIODM_CLK_EXTSIG_2 = 5
DIODM_CLK_EXTSIG_3 = 6
#----------------------------------------
# Internal Clock
#----------------------------------------
DIODM_TIM_UNIT_S = 1
DIODM_TIM_UNIT_MS = 2
DIODM_TIM_UNIT_US = 3
DIODM_TIM_UNIT_NS = 4
#----------------------------------------
# Stop
#----------------------------------------
DIODM_STOP_SOFT = 1
DIODM_STOP_EXT_RISE = 2
DIODM_STOP_EXT_FALL = 3
DIODM_STOP_NUM = 4
DIODM_STOP_EXTSIG_1 = 5
DIODM_STOP_EXTSIG_2 = 6
DIODM_STOP_EXTSIG_3 = 7
#----------------------------------------
# ExtSig
#----------------------------------------
DIODM_EXT_START_SOFT_IN = 1
DIODM_EXT_STOP_SOFT_IN = 2
DIODM_EXT_CLOCK_IN = 3
DIODM_EXT_EXT_TRG_IN = 4
DIODM_EXT_START_EXT_RISE_IN = 5
DIODM_EXT_START_EXT_FALL_IN = 6
DIODM_EXT_START_PATTERN_IN = 7
DIODM_EXT_STOP_EXT_RISE_IN = 8
DIODM_EXT_STOP_EXT_FALL_IN = 9
DIODM_EXT_CLOCK_ERROR_IN = 10
DIODM_EXT_HANDSHAKE_IN = 11
DIODM_EXT_TRNSNUM_IN = 12
DIODM_EXT_START_SOFT_OUT = 101
DIODM_EXT_STOP_SOFT_OUT = 102
DIODM_EXT_CLOCK_OUT = 103
DIODM_EXT_EXT_TRG_OUT = 104
DIODM_EXT_START_EXT_RISE_OUT = 105
DIODM_EXT_START_EXT_FALL_OUT = 106
DIODM_EXT_STOP_EXT_RISE_OUT = 107
DIODM_EXT_STOP_EXT_FALL_OUT = 108
DIODM_EXT_CLOCK_ERROR_OUT = 109
DIODM_EXT_HANDSHAKE_OUT = 110
DIODM_EXT_TRNSNUM_OUT = 111
#----------------------------------------
# Status
#----------------------------------------
DIODM_STATUS_BMSTOP = 0x1
DIODM_STATUS_PIOSTART = 0x2
DIODM_STATUS_PIOSTOP = 0x4
DIODM_STATUS_TRGIN = 0x8
DIODM_STATUS_OVERRUN = 0x10
#----------------------------------------
# Error
#----------------------------------------
DIODM_STATUS_FIFOEMPTY = 0x1
DIODM_STATUS_FIFOFULL = 0x2
DIODM_STATUS_SGOVERIN = 0x4
DIODM_STATUS_TRGERR = 0x8
DIODM_STATUS_CLKERR = 0x10
DIODM_STATUS_SLAVEHALT = 0x20
DIODM_STATUS_MASTERHALT = 0x40
#----------------------------------------
# Reset
#----------------------------------------
DIODM_RESET_FIFO_IN = 0x02
DIODM_RESET_FIFO_OUT = 0x04
#----------------------------------------
# Buffer Ring
#----------------------------------------
DIODM_WRITE_ONCE = 0
DIODM_WRITE_RING = 1
#----------------------------------------
# NET
#----------------------------------------
DIONET_MODE_DIRECT = 0
DIONET_MODE_AP = 1
#----------------------------------------
# Counter
#----------------------------------------
DIO_COUNT_EDGE_UP = 1
DIO_COUNT_EDGE_DOWN = 2


#----------------------------------------
# Error codes
#----------------------------------------
#----------------------------------------
# Initialize Error
#----------------------------------------
DIO_ERR_SUCCESS = 0                             # normal completed
DIO_ERR_INI_RESOURCE = 1                        # invalid resource reference specified
DIO_ERR_INI_INTERRUPT = 2                       # invalid interrupt routine registered
DIO_ERR_INI_MEMORY = 3                          # invalid memory allocationed
DIO_ERR_INI_REGISTRY = 4                        # invalid registry accesse
DIO_ERR_SYS_RECOVERED_FROM_STANDBY = 7          # Execute DioResetDevice function because the device has recovered from standby mode.
DIO_ERR_INI_NOT_FOUND_SYS_FILE = 8              # Because the Cdio.sys file is not found, it is not possible to initialize it.
DIO_ERR_INI_DLL_FILE_VERSION = 9                # Because version information on the Cdio.dll file cannot be acquired, it is not possible to initialize it.
DIO_ERR_INI_SYS_FILE_VERSION = 10               # Because version information on the Cdio.sys file cannot be acquired, it is not possible to initialize it.
DIO_ERR_INI_NO_MATCH_DRV_VERSION = 11           # Because version information on Cdio.dll and Cdio.sys is different, it is not possible to initialize it.
#----------------------------------------
# DLL Error
#----------------------------------------
DIO_ERR_DLL_DEVICE_NAME = 10000                 # invalid device name specified.
DIO_ERR_DLL_INVALID_ID = 10001                  # invalid ID specified.
DIO_ERR_DLL_CALL_DRIVER = 10002                 # not call the driver.(Invalid device I/O controller)
DIO_ERR_DLL_CREATE_FILE = 10003                 # not create the file.(Invalid CreateFile)
DIO_ERR_DLL_CLOSE_FILE = 10004                  # not close the file.(Invalid CloseFile)
DIO_ERR_DLL_CREATE_THREAD = 10005               # not create the thread.(Invalid CreateThread)
DIO_ERR_INFO_INVALID_DEVICE = 10050             # invalid device infomation specified .Please check the spell.
DIO_ERR_INFO_NOT_FIND_DEVICE = 10051            # not find the available device
DIO_ERR_INFO_INVALID_INFOTYPE = 10052           # specified device infomation type beyond the limit
DIO_ERR_DLL_BUFF_ADDRESS = 10100                # invalid data buffer address
DIO_ERR_DLL_HWND = 10200                        # window handle beyond the limit
DIO_ERR_DLL_TRG_KIND = 10300                    # trigger kind beyond the limit
#----------------------------------------
# SYS Error
#----------------------------------------
DIO_ERR_SYS_MEMORY = 20000                      # not secure memory
DIO_ERR_SYS_NOT_SUPPORTED = 20001               # this board couldn't use this function
DIO_ERR_SYS_BOARD_EXECUTING = 20002             # board is behaving, not execute
DIO_ERR_SYS_USING_OTHER_PROCESS = 20003         # other process is using the device, not execute
DIO_ERR_SYS_NOT_FOUND_PROCESS_DATA = 20004      # process information is not found.
#----------------------------------------
# USB
#----------------------------------------
STATUS_SYS_USB_CRC = 20020                      # the last data packet received from end point exist CRC error
STATUS_SYS_USB_BTSTUFF = 20021                  # the last data packet received from end point exist bit stuffing offense error
STATUS_SYS_USB_DATA_TOGGLE_MISMATCH = 20022     # the last data packet received from end point exist toggle packet mismatch error
STATUS_SYS_USB_STALL_PID = 20023                # end point return STALL packet identifier
STATUS_SYS_USB_DEV_NOT_RESPONDING = 20024       # device don't respond to token(IN) ,don't support handshake
STATUS_SYS_USB_PID_CHECK_FAILURE = 20025
STATUS_SYS_USB_UNEXPECTED_PID = 20026           # invalid packet identifier received
STATUS_SYS_USB_DATA_OVERRUN = 20027             # end point return data quantity overrun
STATUS_SYS_USB_DATA_UNDERRUN = 20028            # end point return data quantity underrun
STATUS_SYS_USB_BUFFER_OVERRUN = 20029           # IN transmit specified buffer overrun
STATUS_SYS_USB_BUFFER_UNDERRUN = 20030          # OUT transmit specified buffer underrun
STATUS_SYS_USB_ENDPOINT_HALTED = 20031          # end point status is STALL, not transmit
STATUS_SYS_USB_NOT_FOUND_DEVINFO = 20032        # not found device infomation
STATUS_SYS_USB_ACCESS_DENIED = 20033            # Access denied
STATUS_SYS_USB_INVALID_HANDLE = 20034           # Invalid handle
#----------------------------------------
# DIO
#----------------------------------------
DIO_ERR_SYS_PORT_NO = 20100                     # board No. beyond the limit
DIO_ERR_SYS_PORT_NUM = 20101                    # board number beyond the limit
DIO_ERR_SYS_BIT_NO = 20102                      # bit No. beyond the limit
DIO_ERR_SYS_BIT_NUM = 20103                     # bit number beyond the limit
DIO_ERR_SYS_BIT_DATA = 20104                    # bit data beyond the limit of 0 to 1
DIO_ERR_SYS_INT_BIT = 20200                     # interrupt bit beyond the limit
DIO_ERR_SYS_INT_LOGIC = 20201                   # interrupt logic beyond the limit
DIO_ERR_SYS_TIM = 20300                         # timer value beyond the limit
DIO_ERR_SYS_FILTER = 20400                      # filter number beyond the limit
DIO_ERR_SYS_IODIRECTION = 20500                 # Direction value is out of range
DIO_ERR_SYS_8255 = 20600                        # 8255 chip number is outside of the range.
#----------------------------------------
# DM
#----------------------------------------
DIO_ERR_SYS_SIGNAL = 21000                      # Usable signal is outside the setting range.
DIO_ERR_SYS_START = 21001                       # Usable start conditions are outside the setting range.
DIO_ERR_SYS_CLOCK = 21002                       # Clock conditions are outside the setting range.
DIO_ERR_SYS_CLOCK_VAL = 21003                   # Clock value is outside the setting range.
DIO_ERR_SYS_CLOCK_UNIT = 21004                  # Clock value unit is outside the setting range.
DIO_ERR_SYS_STOP = 21005                        # Stop conditions are outside the setting range.
DIO_ERR_SYS_STOP_NUM = 21006                    # Stop number is outside the setting range.
DIO_ERR_SYS_RESET = 21007                       # Contents of reset are outside the setting range.
DIO_ERR_SYS_LEN = 21008                         # Data number is outside the setting range.
DIO_ERR_SYS_RING = 21009                        # Buffer repetition use setup is outside the setting range.
DIO_ERR_SYS_COUNT = 21010                       # Data transmission number is outside the setting range.
DIO_ERR_DM_BUFFER = 21100                       # Buffer was too large and has not secured.
DIO_ERR_DM_LOCK_MEMORY = 21101                  # Memory has not been locked.
DIO_ERR_DM_PARAM = 21102                        # Parameter error
DIO_ERR_DM_SEQUENCE = 21103                     # Procedure error of execution
#----------------------------------------
# NET
#----------------------------------------
DIO_ERR_NET_BASE = 22000                        # Access error
DIO_ERR_NET_ACCESS = 22001                      # Access violation
DIO_ERR_NET_AREA = 22002                        # Area error
DIO_ERR_NET_SIZE = 22003                        # Access size error
DIO_ERR_NET_PARAMETER = 22004                   # Parameter error
DIO_ERR_NET_LENGTH = 22005                      # Length error
DIO_ERR_NET_RESOURCE = 22006                    # Insufficient resources
DIO_ERR_NET_TIMEOUT = 22016                     # Communications timeout
DIO_ERR_NET_HANDLE = 22017                      # Handle error
DIO_ERR_NET_CLOSE = 22018                       # Close error
DIO_ERR_NET_TIMEOUT_WIO = 22064                 # Wireless communications timeout
