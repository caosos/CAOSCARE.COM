# RF Pendant Protocol Notes

## 900 MHz pendant framing (typical Life-Alert style)

Most OEM pendants in the 902–928 MHz ISM band emit a short OOK (on-off-keyed) burst
containing:

| Field          | Size     | Notes                                         |
|----------------|----------|-----------------------------------------------|
| Preamble       | 16 bits  | `0xAAAA`                                      |
| Sync           | 16 bits  | `0x2DD4`                                      |
| Pendant serial | 24 bits  | Unique per pendant (vendor-coded)             |
| Event code     | 4 bits   | `0x1=press`, `0x2=fall`, `0xF=heartbeat`      |
| Battery        | 8 bits   | 0-100 %                                       |
| CRC            | 8 bits   | CRC-8                                         |

Frequencies are typically spaced 12.5 kHz apart. CAOS Care keys off the **channel
frequency** that the receiver reports, not the pendant serial, so each pendant can be
paired to a resident by simply registering its frequency in Admin → Pendants.

## Receiver firmware output format

Whatever MCU + transceiver combo you use, the firmware must expose a USB-CDC (virtual
COM) port and emit one JSON object per detected press, followed by `\n`:

```json
{"frequency_mhz": 916.1250, "signal_strength": 82, "battery_percent": 87, "event_type": "press"}
```

Optional periodic heartbeats every 30 s:

```json
{"frequency_mhz": 916.1250, "signal_strength": 78, "battery_percent": 87, "event_type": "periodic_ping"}
```

Keeps the pendant's battery/signal telemetry fresh on the backend without creating
a staff alert.

## Reference Arduino sketch (RFM69 + Uno/Pro Micro)

```cpp
#include <RFM69.h>
RFM69 radio;

void setup() {
  Serial.begin(115200);
  radio.initialize(RF69_915MHZ, 1, 100);
  radio.setPowerLevel(20);
}

void loop() {
  if (radio.receiveDone()) {
    float freq = radio.getFrequency() / 1e6;
    int rssi = radio.readRSSI();
    // Parse vendor framing -> eventCode, batt
    Serial.print('{');
    Serial.print("\"frequency_mhz\":"); Serial.print(freq, 4); Serial.print(',');
    Serial.print("\"signal_strength\":"); Serial.print(map(rssi, -100, -40, 0, 100)); Serial.print(',');
    Serial.print("\"battery_percent\":"); Serial.print(batt); Serial.print(',');
    Serial.print("\"event_type\":\""); Serial.print(evt); Serial.print('"');
    Serial.println('}');
  }
}
```

Replace the vendor framing stanza with your pendant's actual bit layout if it differs.
