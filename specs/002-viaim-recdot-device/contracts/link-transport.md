# Contract: RecDot link transport

The native layer on each platform is a dumb byte pipe. Everything that understands the buds
lives in Dart above it.

## Dart-facing surface

Implements Omi's `DeviceTransport` (`lib/services/devices/transports/device_transport.dart`).

| Method | Behaviour for the RecDot |
|---|---|
| `connect()` | iOS: open an `EASession` on `com.vision.voyager` for the accessory matching `deviceId`. Android: open an insecure RFCOMM socket on `00001101-0000-1000-8000-00805F9B34FB`, falling back to the two vendor UUIDs in protocol.md §2.1 |
| `disconnect()` | Close streams/socket; emit `disconnecting` then `disconnected` |
| `isConnected()` | True only while the session/socket is open |
| `ping()` | True if the session/socket is open; the connection layer does the real liveness check (`0x5505`) |
| `getCharacteristicStream('viaim-recdot-link', 'viaim-recdot-bytes')` | Raw bytes as received, in arrival order, unframed, never coalesced across a disconnect |
| `writeCharacteristic('viaim-recdot-link', 'viaim-recdot-bytes', bytes)` | Write exactly these bytes; complete only after the platform accepted them |
| `readCharacteristic(...)` | Returns empty; the link has no readable attributes |
| `connectionStateStream` | `DeviceTransportState` transitions, including platform-initiated disconnects |
| `requestBond()` | Returns true; bonding is the OS headset pairing, already done |

Any other service/characteristic id is rejected with an error naming it.

## Pigeon surface (`lib/pigeon_interfaces.dart`)

```
@HostApi()  RecDotLinkHostAPI
  List<RecDotAccessory> listAccessories()          // iOS: EA accessories with the protocol; Android: bonded+connected headsets matching identity heuristics
  void connect(String deviceId)
  void disconnect(String deviceId)
  void write(String deviceId, Uint8List bytes)

@FlutterApi() RecDotLinkFlutterAPI
  void onBytes(String deviceId, Uint8List bytes)
  void onConnectionStateChanged(String deviceId, String state)   // connecting|connected|disconnecting|disconnected
  void onAccessoryListChanged()
```

`RecDotAccessory { String deviceId; String name; String? serialNumber; String? firmwareRevision; }`

Rules:
- The Flutter API is a process-wide singleton (as with Ray-Ban Meta); the Dart transport keeps
  static controller registries keyed by `deviceId`.
- Native code never parses frames, never retries commands, never sleeps in the read path.
- iOS reads on a dedicated thread's run loop, draining `hasBytesAvailable` completely per event.
- Android reads with a 1024-byte buffer on a dedicated thread, matching the vendor app.

## Info.plist additions (iOS)

```
UISupportedExternalAccessoryProtocols: [ com.vision.voyager ]
UIBackgroundModes: + external-accessory
```
