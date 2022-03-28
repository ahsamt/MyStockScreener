document.addEventListener("DOMContentLoaded", () => {
  // check on scroll if "back to top" button should be displayed
  window.addEventListener("scroll", () => top_scroll());


  // add clarifying message re S&P 500 on the search page
  if (document.querySelector(".question")) {
    document.querySelector(".question").addEventListener("click", (event) => {
      event.preventDefault();
      alert(
        "Please take a look at the Ticker List page of this application to see a full list of S&P 500 companies"
      );
    });
  }

  document.querySelectorAll(".graph-button").forEach((graph_button) => {
    graph_button.addEventListener("click", (event) => show_graph(event));
  });

  document.querySelectorAll(".close-graph").forEach((graph_button) => {
    graph_button.addEventListener("click", (event) => hide_graphs(event));
  });

  document.querySelectorAll(".ind_outcome_button").forEach((outcome_button) => {
    outcome_button.addEventListener("click", (event) => show_outcome_table(event));
  });

  document.querySelectorAll(".close_ind_outcome_button").forEach((close_ind_outcome_button)=> {
    close_ind_outcome_button.addEventListener("click", (event) => hide_outcome_table(event));
  });

   document.querySelectorAll(".remove-ticker-button").forEach((remove_button) => {
    remove_button.addEventListener("click", (event) => {remove_from_watchlist(event)

 } );
  });


   function remove_from_watchlist(event) {
      let confirm = prompt(
      `Are you sure you want to remove this stock from your watchlist? This will permanently delete any notes you have saved. (y/n)`
      );
      if (confirm === "y") {
      update_watchlist(event);

        } else if (confirm === "n") {
      alert("No problem, we'll keep it where it is!");
      } else {
      alert("Sorry, we didn't get it! Please try again.");
    }
  }

  function update_watchlist(event) {
  event.preventDefault();

  let tickerID = event.target.dataset.ticker_id;
  let user = document.getElementById("username").innerHTML;
  let section_to_remove = event.target.parentElement.parentElement;
  fetch(`/saved_searches/${tickerID}`, {
      method: "DELETE",
    }).then((response) => {
      if (response.ok) {
        section_to_remove.remove();
        }
      }
    );
  }

  function show_outcome_table(event) {
    event.preventDefault();
    let ticker = event.target.dataset.ticker;
    let ind_outcome_table = document.getElementById(`${ticker}_card`);
    let main_outcome_table = document.getElementById("main_outcome_section");
    ind_outcome_table.style.display = "block";
    main_outcome_table.style.display = "none";

  }

  function hide_outcome_table(event) {
    event.preventDefault();
    let main_outcome_table = document.getElementById("main_outcome_section");
    document.querySelectorAll(".ind_result").forEach((table) => {table.style.display = "none"});
    main_outcome_table.style.display = "block";
  }





  function show_graph(event) {
    event.preventDefault();
    let ticker = event.target.dataset.ticker;
    let graph = document.getElementById(`${ticker}_graph`);
    let table = document.getElementById("result-table");
    graph.style.display = "block";
    table.style.display = "none";
  }

  function hide_graphs(event) {
    event.preventDefault();
    document.querySelectorAll(`.graphs`).forEach((g) => {
      g.style.display = "none"});
    document.getElementById("result-table").style.display = "block";

  }
  // update watchlist when the relevant button is clicked on the index page
  document.querySelectorAll(".watchlist").forEach((watch_button) => {
    watch_button.addEventListener("click", (event) => update_watchlist(event));
  });

  // remove stock from watchlist when the relevant button is clicked on the watchlist page
  document
    .querySelectorAll(".remove_from_watchlist")
    .forEach((remove_button) => {
      remove_button.addEventListener("click", (event) => {
        remove_from_watchlist(event);
      });
    });


    // save current signal when the relevant button is clicked on the index page
  document.querySelectorAll(".add-signal").forEach((add_signal_button) => {
    add_signal_button.addEventListener("click", (event) => add_signal(event));
  });


  // save notes when the relevant button is clicked on the watchlist page
  document.querySelectorAll(".save_notes_button").forEach((save_button) => {
    save_button.addEventListener("click", (event) => update_notes(event));
  });

  // display the relevant stocks when a letter button is clicked on the ticker list page
  document.querySelectorAll(".abc").forEach((letter) => {
    letter.addEventListener("click", (event) => {
      display_stock_list(event);
    });
  });
});

function top_scroll() {
  // insert "back to top" button when user scrolls down the page
  if (document.body.scrollTop > 20 || document.documentElement.scrollTop > 20) {
    document.getElementById("topButton").style.display = "block";
  } else {
    document.getElementById("topButton").style.display = "none";
  }
}

function format_time(time) {
  // formats hours/second/minutes as a 2-digit number
  return time < 10 ? "0" + time : time;
}

function get_time() {
  // get user's current time
  let now = new Date();
  let hours = format_time(now.getHours());
  let minutes = format_time(now.getMinutes());
  return `${hours}:${minutes}`;
}

function update_notes(event) {
  // use internal API to update user's notes for specific stock
  event.preventDefault();
  let tickerID = event.target.dataset.ticker_id;
  let updated_notes = document.getElementById(`editContent${tickerID}`).value;
  fetch(`/saved_searches/${tickerID}`, {
    method: "PUT",
    body: JSON.stringify({
      notes: updated_notes,
    }),
  }).then((response) => {
    if (response.ok) {
      let time = get_time();
      document.getElementById(
        `messageNotes${tickerID}`
      ).innerHTML = `Notes saved at ${time}`;
    }
  });
}

function update_watchlist(event) {
  event.preventDefault();
  console.log("Hello")
  let ticker = event.target.dataset.ticker_name;
  let tickerID = event.target.dataset.ticker_id;
  let tickerFull = event.target.dataset.ticker_full;
  let user = document.getElementById("username").innerHTML;
  console.log(tickerID)
  // Check via internal API if this stock is in user's watchlist
  if (tickerID === "None") {
    console.log("creating a post request")
    fetch("/saved_searches", {
      method: "POST",
      body: JSON.stringify({
        ticker: ticker,
        ticker_full: tickerFull,
      }),
    })
      .then((response) => response.json())
      .then((result) => {
        if (result.message === "Search saved successfully") {
          event.target.dataset.ticker_id = result.id;
          event.target.innerHTML = `Remove ${ticker} from watchlist`;
        }
      });
  } else {
    fetch(`/saved_searches/${tickerID}`, {
      method: "DELETE",
    }).then((response) => {
      if (response.ok) {
        event.target.dataset.ticker_id = "None";
        if (ticker !== undefined) {
          event.target.innerHTML = `Add ${ticker} to watchlist`;
        }
      }
    });
  }
}

function remove_from_watchlist(event) {
  let stockID = event.target.dataset.ticker_id;
  let confirm = prompt(
    `Are you sure you want to remove this ticker from your watchlist? This will permanently delete any notes you have saved. (y/n)`
  );
  if (confirm === "y") {
    update_watchlist(event);
    document.getElementById(`watchedItem${tickerID}`).style.animationPlayState =
      "running";
    document.getElementById(`stock_link${tickerID}`).style.display = "none";
  } else if (confirm === "n") {
    alert("No problem, we'll keep it where it is!");
  } else {
    alert("Sorry, we didn't get it! Please try again.");
  }
}

function display_stock_list(event) {
  event.preventDefault();
  document.querySelectorAll(".abc_tickers").forEach((section) => {
    section.style.display = "none";
  });
  document.getElementById(`${event.target.dataset.letter}`).style.display =
    "block";
}

function add_signal(event) {
  event.preventDefault();
  let ma = event.target.dataset.ma;
  let maS = event.target.dataset.mas;
  let maL = event.target.dataset.mal;
  let maWS = event.target.dataset.maws;
  let maWL = event.target.dataset.mawl;
  let psar = event.target.dataset.psar;
  let psarAF = event.target.dataset.psaraf;
  let psarMA = event.target.dataset.psarma;
  let adx = event.target.dataset.adx;
  let adxW = event.target.dataset.adxw;
  let adxL = event.target.dataset.adxl;

  let srsi = event.target.dataset.srsi;
  let srsiW = event.target.dataset.srsiw;
  let srsiSm1 = event.target.dataset.srsism1;
  let srsiSm2 = event.target.dataset.srsism2;
  let srsiOB = event.target.dataset.srsiob;
  let srsiOS = event.target.dataset.srsios;

  let macd = event.target.dataset.macd;
  let macdF = event.target.dataset.macdf;
  let macdS = event.target.dataset.macds;
  let macdSm = event.target.dataset.macdsm;

  let previousSignal = event.target.dataset.previoussignal;

  let user = document.getElementById("username").innerHTML;

  //
    console.log("creating a post request")
    fetch("/saved_signals", {
      method: "POST",
      body: JSON.stringify({
          ma : ma,
          maS : maS,
          maL : maL,
          maWS : maWS,
          maWL : maWL,
          psar : psar,
          psarAF : psarAF,
          psarMA : psarMA,
          adx : adx,
          adxW : adxW,
          adxL : adxL,

          srsi : srsi,
          srsiW : srsiW,
          srsiSm1 : srsiSm1,
          srsiSm2 : srsiSm2,
          srsiOB : srsiOB,
          srsiOS : srsiOS,

          macd : macd,
          macdF : macdF,
          macdS : macdS,
          macdSm : macdSm,
          previousSignal: previousSignal,
      }),
    })
      .then((response) => response.json())
      .then((result) => {
        if (result.message === "Signal saved successfully") {
          event.target.dataset.previousSignal = result.id;
          event.target.style.display = "none";
          document.getElementById("signal_saved_message").style.display = "block";
        }
      });


}
