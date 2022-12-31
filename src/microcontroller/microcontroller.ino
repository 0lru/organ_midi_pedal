#include <EEPROM.h>

char const eeprom_version_signature[] = "1.0.0";
#define cbi(sfr, bit) (_SFR_BYTE(sfr) &= ~_BV(bit))
#define sbi(sfr, bit) (_SFR_BYTE(sfr) |= _BV(bit))


//////////////////////////////////////////////////////////////////////////////////////////
// utils
using millis_t = unsigned long;

class Counter
{
public:
  void increment(millis_t now);
  float hz() const;

private:
  millis_t _last_update_time = 0;
  int _frame_count = 0;
  float _hz = 0.f;
};

void Counter::increment(millis_t now)
{
  ++_frame_count;
  int delta = now - _last_update_time;
  if (delta > 1000)
  {
    _hz = float(_frame_count / (double(delta) / 1000.0));
    _frame_count = 0;
    _last_update_time = now;
  }
}

float Counter::hz() const
{
  return _hz;
}


//////////////////////////////////////////////////////////////////////////////////////////
// state
bool debug = false;
int const default_threshold = 200;
int const address_pins[8] = {10, 11, 12};

int const key_count = 20;
auto const calibration_percentage = 0.5;

struct Key
{
  int value = 0;                     // actual value
  int value_min = 100;               // calibrated minimum reference value (minimum voltage)
  int value_max = 512;               // calibrated maximum reference value (maximum voltage)
  int threshold = default_threshold; // actual voltage threshold, range is [value_min, value_max]
  int state = LOW;                   // actual state
  int state_debounce_time = 0;       // actual debounce timeout
};

Key pedal[key_count];
Counter counter;


//////////////////////////////////////////////////////////////////////////////////////////
// eeprom resp. persistency

//
// checks if calibration was stored to eeprom
bool is_calibrated()
{
  auto signature_length = strlen(eeprom_version_signature);
  for (int address = 0; address < signature_length; ++address)
    if (EEPROM.read(address) != eeprom_version_signature[address])
      return false;
  return true;
}

//
// store calibration to eeprom
void store_calibration()
{
  auto signature_length = strlen(eeprom_version_signature);
  int address = 0;

  for (; address < signature_length; ++address)
    EEPROM.write(address, eeprom_version_signature[address]);

  for (int i = 0; i < key_count; ++i, address += sizeof(int))
    EEPROM.put(address, pedal[i].threshold);

  for (int i = 0; i < key_count; ++i, address += sizeof(int))
    EEPROM.put(address, pedal[i].value_min);
}

//
// restore calibration from eeprom
void restore_calibration()
{
  if (!is_calibrated())
    return;

  int address = strlen(eeprom_version_signature);

  for (int i = 0; i < key_count; ++i, address += sizeof(int))
    EEPROM.get(address, pedal[i].threshold);

  for (int i = 0; i < key_count; ++i, address += sizeof(int))
    EEPROM.get(address, pedal[i].value_min);
}


//////////////////////////////////////////////////////////////////////////////////////////
// command interface

void send_thresholds()
{
  Serial.print('t');
  for (int i = 0; i < key_count; ++i)
  {
    Serial.print(pedal[i].threshold);
    Serial.print(' ');
  }
  Serial.print('\n');
}

void send_values()
{
  Serial.print('v');
  Serial.print(millis());
  Serial.print(' ');
  for (int i = 0; i < key_count; ++i)
  {
    Serial.print(pedal[i].value);
    Serial.print(' ');
  }
  Serial.print('\n');
}

inline void send_state(int key_index)
{
  Serial.print(pedal[key_index].state == HIGH ? "p" : "r");
  Serial.print(key_index);
  Serial.print('\n');
}

void send_state()
{
  for (int i = 0; i < key_count; ++i)
    send_state(i);
}

void send_debug()
{
  Serial.print('d');
  Serial.print(debug);
  Serial.print('\n');
}

void send_version()
{
  Serial.print('i');
  Serial.print(eeprom_version_signature);
  Serial.print('\n');
}

void send_hz()
{
  Serial.print('h');
  Serial.print(int(counter.hz()));
  Serial.print('\n');
}

void calibrate()
{
  for (int i = 0; i < key_count; ++i)
  {
    auto &key = pedal[i];
    key.value_min = key.value;
    key.threshold = int((key.value_max - key.value_min) * calibration_percentage) + key.value_min;
  }
  send_thresholds();
}

void process_command()
{
  char command = Serial.read();
  switch (command)
  {
  case 'm':
  {
    int key_index = Serial.parseInt(SKIP_NONE);
    Serial.read();
    int threshold = Serial.parseInt(SKIP_NONE);
    Serial.read(); // skip '\n'
    pedal[key_index].threshold = threshold;
    break;
  }
  case 'w':
  {
    Serial.read(); // skip '\n'
    store_calibration();
    break;
  }
  case 'c':
  {
    Serial.read(); // skip '\n'
    calibrate();
    break;
  }
  case 'd':
  {
    Serial.read(); // skip '\n'
    debug = !debug;
    send_debug();
    break;
  }
  case 'i':
  {
    Serial.read(); // skip '\n'
    send_version();
    break;
  }
  case 'v':
  {
    Serial.read(); // skip '\n'
    send_values();
    break;
  }
  case 's':
  {
    Serial.read(); // skip '\n'
    send_state();
    break;
  }
  case 't':
  {
    Serial.read(); // skip '\n'
    send_thresholds();
    break;
  }
  case 'h':
  {
    Serial.read(); // skip '\n'
    send_hz();
    break;
  }
  default:
  {
    break;
  }
  }
}


//////////////////////////////////////////////////////////////////////////////////////////
// read sensor values & update state

void read_sensor_values()
{
  //
  // the first 16 buttons are demultiplexed by two 4051 ic's.
  for (int i = 0; i < 8; ++i)
  {
    digitalWrite(address_pins[0], bitRead(i, 0));
    digitalWrite(address_pins[1], bitRead(i, 1));
    digitalWrite(address_pins[2], bitRead(i, 2));
    delayMicroseconds(1);
    pedal[i].value = analogRead(A0);
    pedal[i + 8].value = analogRead(A1);
  }

  //
  // rest (16-19) is directly connected to analog inputs (A2-A5)
  pedal[16].value = analogRead(A2);
  pedal[17].value = analogRead(A3);
  pedal[18].value = analogRead(A4);
  pedal[19].value = analogRead(A5);
}

inline void update_key_state(millis_t time, int key_index)
{
  Key &key = pedal[key_index];

  //
  // debounce with 10 ms
  if (time - key.state_debounce_time < 10)
    return;

  //
  // check current voltage is below the calibrated threshold
  int state = key.value > key.threshold ? HIGH : LOW;

  //
  // do nothing if state is same
  if (state == key.state)
    return;

  //
  // update state for debouncing
  key.state = state;
  key.state_debounce_time = time;

  send_state(key_index);
}


//////////////////////////////////////////////////////////////////////////////////////////
// arduino setup / loop

void setup()
{
  // thatd' be 2000hz, but 500Hz is also fine:
  // sbi(ADCSRA, ADPS2);
  // cbi(ADCSRA, ADPS1);
  // cbi(ADCSRA, ADPS0);
  Serial.begin(500000);
//  Serial.begin(19200);

  pinMode(address_pins[0], OUTPUT);
  pinMode(address_pins[1], OUTPUT);
  pinMode(address_pins[2], OUTPUT);

  restore_calibration();

  //
  // the new serial connection will cause a reset.
  // this initing values on the connection here
  send_version();
  send_thresholds();
  send_debug();
  send_state();
}

void loop()
{
  auto time = millis();
  counter.increment(time);

  read_sensor_values();

  for (int i = 0; i < key_count; ++i)
    update_key_state(time, i);

  while (Serial.available())
    process_command();

  if (debug)
    send_values();
}
