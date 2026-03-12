/* ----------------------------- 
   Monitor Javascript Routines 
   ----------------------------- */

var millisecondsPerDay = 24 * 60 * 60 * 1000;

// Chart data
var data2 = [];
var myLineChart;
var energy = [];

function initChart() {
  let ctx = document.querySelector('canvas').getContext('2d');

  var plugin = {
      id: 'energy_plugin',
      afterDraw: function(chart) {
      /* afterUpdate: function(chart) { */

        if (!($('#energy').is(":checked"))) { return true }
        if (energy === undefined){ return true }

        //ctx = chart.chart.ctx
        ctx = chart.ctx;
        //xScale = chart.scales['x-axis-0'];
        //yScale = chart.scales['y-axis-0'];
        xScale = chart.scales['x'];
        yScale = chart.scales['y'];

        ctx.restore();
        //ctx.font = "bold 14px Arial";
        ctx.fillStyle = "brown";
        ctx.textAlign = "center";
        ctx.textBaseline = "bottom";

        for (let i = 0; i < energy.length; i++) {
          // [size, xvalue, number]
          ctx.font = (Math.floor(energy[i][2] * 9) + 7) + "px Arial";
          //ctx.font = (Math.floor(energy[i][2]/8) + 6) + "px LiberationSansNarrow";
          ctx.fillText(
            energy[i][2].toFixed(1),
            xScale.getPixelForValue(energy[i][1]),
            yScale.getPixelForValue(4)
          );
        };
        ctx.save();
      }
  };

  myLineChart = new Chart(ctx, {
    options: { response: true,
               maintainAspectRatio: false
             }, 
    type: 'line',
    plugins: [plugin],

    /* scales: {
             x: {
                  ticks: {
                           maxTicksLimit: 20,
                           source: 'labels'
                         }
                }
            }, */
    data: {
      labels: data2.Dates,
      datasets: [{
          label: '01 00',
          data: data2.Values,
          borderColor: 'red',
          fill: false,
          animations: false
        }]
    }
  });
}

// Redraw the chart with server data
function fetchMonitor(event) {
  if (event != 'start') event.target.disabled = true;

  let range1 = $("input[name='range1']").val();
  let range2 = $("input[name='range2']").val();

  let parms = [];
  $.each($("input[name='parms']:checked"), function(){
    parms.push($(this).val());
  });

  let time1 = 'X';
  let time2 = 'X';
  // time filter?
  if ($('#time').is(":checked")) {
    time1 = $("input[name='time1']").val();
    time2 = $("input[name='time2']").val();
  }

  let energyflag = 'N';
  if ($('#energy').is(":checked")) energyflag = 'Y';

  let smoothing = 'N';
  if ($('#smooth').is(":checked")) smoothing = 'Y';

  var request = $.ajax({
          type: "GET",
          url: "/ws_monitor",
          data: { range1, range2, time1, time2, energyflag, parms, smoothing },
          dataType: "JSON"
        });
  request.done(function(msg) {

    // how many ticks to use on chart
    let ticks = msg.Ticks;

    // grab energy, if there
    energy = msg.Energy;

    // first truncate to remove all the data
    myLineChart.data.datasets.length = 0;

    // then load with the server data
    for (let i = 0; i < msg.Datasets.length; i++) {
      let filling = (msg.Datasets[i].Id == '01 03') ? true : false
      let bkgrnd  = (msg.Datasets[i].Id == '01 03') ? 'rgba(255, 192, 203, 0.7)' : 'white'
      //let tension = (msg.Datasets[i].Id == '01 06') ? 0.4 : 0
      let tension = 0
      //let backgroundColor: 'pink'
      myLineChart.data.datasets.push(
                                     { animations: false,
                               /*   backgroundColor: 'pink',   */
                                  backgroundColor: bkgrnd,
                                      borderColor: msg.Datasets[i].Colour,
                                      borderWidth: 1,
                                             data: msg.Datasets[i].Values,
                                             fill: filling,
                                            label: msg.Datasets[i].Parameter,
                                       pointStyle: false,
                                          tension: tension
                                     }
                                    )
    }
    myLineChart.options.scales.x.ticks.maxTicksLimit = ticks;
    //myLineChart.options.scales.x.ticks.align = 'inner';
    myLineChart.data.labels = msg.Dates;
    myLineChart.update();

    // performance figures (if showing a single day)
    perf = msg.Performance;

    $('#performance').hide();
    if (!(perf === undefined)){ 
      $('#energy_in').html(perf['in']);
      $('#energy_out').html(perf['out']);
      $('#cop').html(perf['cop']);
      $('#performance').show();
    }

    if (event != 'start') event.target.disabled = false;
  }),
  request.fail(function( jqXHR, textStatus ) {
    alert("Failed: Please reload page and try again.");
  });

};

function paging(direction) {

  let range1 = $("input[name='range1']").val() + ' 04:00';   // avoid dates/times around BST/GMT time change!
  let range2 = $("input[name='range2']").val() + ' 04:00';

  let d1 = new Date(range1);
  let d2 = new Date(range2);
  let range = (d2 - d1) / millisecondsPerDay;
  //if (range == 0) range = 1;
  range++;

  if (direction == 'back') range = -range;

  d1.setDate(d1.getDate() + range);
  d2.setDate(d2.getDate() + range);

  range1 = d1.toISOString().substr(0,10);
  range2 = d2.toISOString().substr(0,10);

  let now = new Date();
  now = now.toISOString().substr(0,10);
  if (range1 > now) {range1 = now};
  if (range2 > now) {range2 = now};

  $("input[name='range1']").val(range1);
  $("input[name='range2']").val(range2);

  fetchMonitor('start');

}

// If a collection is selected, update the parms selected based on the collection value
function updateParms(event) {

  let parms = $('.collections').find(':selected').val();
  parms = parms.split(',');

  $('input[type=checkbox]:checked').prop('checked', false);

  for (let i = 0; i < parms.length; i++) {
    $('input[name=parms][value="'+parms[i]+'"]').prop('checked', true);
  };

  return true;
};
