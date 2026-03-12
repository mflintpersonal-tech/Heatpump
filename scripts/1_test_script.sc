/* Script to scan for BLE advertisement data of some Switchbot thermomenters, and pass on via HTTP
*/
const switchbot_macs = ['d6:34:c4:c6:3e:9a'];

function ble_handler(event, result){
  if (event == BLE.Scanner.SCAN_START) {
    print("Scan started");
  } else if (event == BLE.Scanner.SCAN_RESULT) {
    if (switchbot_macs.indexOf(result.addr) != -1) {
      //print(btoh(result.manufacturer_data["0969"]));
      //print('Adv Data =');
      //print(btoh(result.advData));
      //print(result.service_data);      /* seems missing right now, so no battery status cf PiW/Pi4 */
      let value = btoa(result.manufacturer_data["0969"]);
      /* send to Pi4 */
      Shelly.call("HTTP.POST",
                   { url: "http://192.168.1.150/ws/t/ble/"+result.addr,
                     body: JSON.stringify({manufacturer:value})
                   },
                   function (res, error_code, error_msg, ud) {
                     if (error_code != 0) {
                       print('BAD response:')
                       print(error_code);
                       print(error_msg);
                     };
                   }
                 );
    }
  }
}

result = BLE.Scanner.Start( {duration_ms: BLE.Scanner.INFINITE_SCAN,
                  /*           interval_ms: 500,        /* scan every 500 ms */
                  /*             window_ms: 50          /* scan for 50 ms */
                             },   
                            ble_handler);
if (result != 0) {
  print(result);
}
