document.addEventListener("DOMContentLoaded", () => {
  const socket = io();

  const confirmationModalElement = document.getElementById("confirmationModal");
  const confirmationModal = confirmationModalElement
    ? new bootstrap.Modal(confirmationModalElement)
    : null;

  // --- START: ADD THIS NEW MODAL STACKING LOGIC ---

  if (confirmationModalElement) {
    // When the confirmation modal is about to be shown...
    confirmationModalElement.addEventListener("show.bs.modal", () => {
      // Find any other modals that are already open.
      const openModals = document.querySelectorAll(".modal.show");
      openModals.forEach((modal) => {
        // ...and apply our 'behind' class to them.
        modal.classList.add("modal-behind");
      });
    });

    // When the confirmation modal has been hidden...
    confirmationModalElement.addEventListener("hidden.bs.modal", () => {
      // Find any modals that have our 'behind' class...
      const behindModals = document.querySelectorAll(".modal-behind");
      behindModals.forEach((modal) => {
        // ...and remove it, bringing them back to the front.
        modal.classList.remove("modal-behind");
      });
    });
  }

  // --- END: ADD THIS NEW MODAL STACKING LOGIC ---
  const confirmDeleteBtn = document.getElementById("confirmDeleteBtn");
  let formToSubmit = null;
  let callbackToExecute = null;

  const showToast = (message, type = "info") => {
    const toastContainer = document.querySelector(".toast-container");
    if (!toastContainer) return;
    const toastClassMap = {
      success: "text-bg-success",
      danger: "text-bg-danger",
      warning: "text-bg-warning",
      info: "text-bg-secondary",
    };
    const toastClass = toastClassMap[type] || "text-bg-secondary";

    // NOTE: We are back to creating the simple toast HTML, no wrapper.
    const toastHTML = `
      <div class="toast ${toastClass}" role="alert" aria-live="assertive" aria-atomic="true">
        <div class="d-flex">
          <div class="toast-body">
            ${message}
          </div>
          <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
      </div>
    `;
    const toastElement = document
      .createRange()
      .createContextualFragment(toastHTML).firstElementChild;

    toastContainer.appendChild(toastElement);

    const toast = new bootstrap.Toast(toastElement, { delay: 5000 });

    toastElement.addEventListener("hidden.bs.toast", () =>
      toastElement.remove()
    );

    toast.show();
  };

  // ADD these two new functions to main.js

  /**
   * Converts a UTC ISO timestamp string into a localized time string (e.g., "2:15 PM").
   * @param {string} isoString - The UTC timestamp in ISO 8601 format.
   * @returns {string} The formatted local time.
   */
  const formatLocalTime = (isoString) => {
    if (!isoString) return "";
    const date = new Date(isoString);
    // Use navigator.language to respect user's locale (e.g., en-US vs en-GB)
    return date.toLocaleTimeString(navigator.language, {
      hour: "numeric",
      minute: "2-digit", // Use '2-digit' for leading zeros (e.g., 14:05)
      hour12: false, // This is the key change to force 24-hour format
    });
  };

  /**
   * Finds all elements with the class 'local-time' and converts their content.
   */
  const convertAllTimestamps = () => {
    document.querySelectorAll(".local-time").forEach((el) => {
      const isoString = el.dataset.timestamp;
      if (isoString) {
        el.textContent = formatLocalTime(isoString);
      }
    });
  };

  // Convert all timestamps on the page to the user's local time
  convertAllTimestamps(); // <-- ADD THIS LINE

  // START: ADD THIS NEW CODE BLOCK
  // Check if the server rendered any flash messages into the window object
  if (window.flashMessages && window.flashMessages.length > 0) {
    window.flashMessages.forEach(function (flash) {
      // Call your existing showToast function for each message
      showToast(flash.message, flash.category);
    });
  }
  // END: ADD THIS NEW CODE BLOCK

  // Handle Custom Frequency Dropdown
  const freqSelect = document.getElementById("frequency_days");
  const customInput = document.getElementById("custom_freq_input");

  if (freqSelect && customInput) {
    freqSelect.addEventListener("change", function () {
      if (this.value === "custom") {
        customInput.classList.remove("d-none");
        customInput.required = true;
        this.removeAttribute("name");
        customInput.setAttribute("name", "frequency_days");
      } else {
        customInput.classList.add("d-none");
        customInput.required = false;
        this.setAttribute("name", "frequency_days");
        customInput.removeAttribute("name");
      }
    });
  }

  const notificationManager = {
    _getStorageKey: (feature, familyId) =>
      `lastSeen_${feature}_family_${familyId}`,
    showNotification: (feature) => {
      const selector =
        feature === "dashboard"
          ? '.nav-link[href="/dashboard"]'
          : `.nav-link[href*="/${feature}"]`;
      const navLink = document.querySelector(selector);
      if (navLink && !navLink.querySelector(".notification-dot")) {
        navLink.innerHTML +=
          ' <span class="notification-dot text-primary">•</span>';
      }
    },
    clearCurrentPageNotification: () => {
      const familyId = document.body.dataset.familyId;
      if (!familyId) return;
      let feature = null;
      if (window.location.pathname === "/dashboard") feature = "dashboard";
      if (window.location.pathname.includes("/calendar")) feature = "calendar";
      if (window.location.pathname.includes("/bulletin_board"))
        feature = "bulletin_board";
      if (feature) {
        localStorage.setItem(
          notificationManager._getStorageKey(feature, familyId),
          new Date().toISOString()
        );
        const selector =
          feature === "home"
            ? '.nav-link[href="/"]'
            : `.nav-link[href*="/${feature}"]`;
        const navLink = document.querySelector(selector);
        const dot = navLink ? navLink.querySelector(".notification-dot") : null;
        if (dot) dot.remove();
      }
    },
    checkAllOnLoad: () => {
      const familyId = document.body.dataset.familyId;
      if (!familyId || typeof window.latestActivity === "undefined") return;
      for (const feature in window.latestActivity) {
        const latestTimestamp = window.latestActivity[feature];
        if (latestTimestamp) {
          const lastSeen = localStorage.getItem(
            notificationManager._getStorageKey(feature, familyId)
          );
          if (!lastSeen || latestTimestamp > lastSeen) {
            notificationManager.showNotification(feature);
          }
        }
      }
    },
    handleRealtimeEvent: (feature, newTimestamp) => {
      const familyId = document.body.dataset.familyId;
      if (!familyId) return;
      const isOnPage = window.location.pathname.includes(`/${feature}`);
      if (isOnPage) {
        localStorage.setItem(
          notificationManager._getStorageKey(feature, familyId),
          new Date().toISOString()
        );
        return;
      }
      const lastSeen = localStorage.getItem(
        notificationManager._getStorageKey(feature, familyId)
      );
      if (!lastSeen || newTimestamp > lastSeen) {
        notificationManager.showNotification(feature);
      }
    },
  };

  socket.on("connect", () => {
    console.log("Connected to server!");
    document
      .querySelectorAll(".list-group[data-list-id]")
      .forEach((list) => socket.emit("join", { list_id: list.dataset.listId }));
    const familyId = document.body.dataset.familyId;
    if (familyId) socket.emit("join_family_room", { family_id: familyId });
  });
  socket.on("list_deleted", (data) =>
    document.getElementById(`list-card-${data.list_id}`)?.remove()
  );
  socket.on("list_added", (data) => {
    // Echo protection: Check if a card for this list already exists
    if (document.getElementById(`list-card-${data.list_id}`)) {
      return;
    }

    const listsContainer = document.getElementById("lists-container");
    if (listsContainer) {
      document.getElementById("no-lists-message")?.remove();
      listsContainer.insertAdjacentHTML("beforeend", data.card_html);
    }
  });
  socket.on("item_added", (data) => {
    const listElement = document.getElementById(`items-list-${data.list_id}`);
    if (listElement && !document.getElementById(`item-${data.item.id}`)) {
      const newItemElement = createListItemElement(data.item);
      listElement.appendChild(newItemElement);
    }
  });
  socket.on("item_edited", (data) => {
    const itemCard = document.getElementById(`item-${data.item_id}`);
    if (itemCard) {
      // Update the data in both places
      itemCard.querySelector(".item-text-display").textContent = data.new_text;
      const editForm = itemCard.querySelector(".item-edit-form");
      editForm.querySelector('input[name="new_text"]').value = data.new_text;

      // --- Force UI back to display state ---
      const textDisplay = itemCard.querySelector(".item-text-display");
      const checkInput = itemCard.querySelector(".form-check-input");
      const actions = itemCard.querySelector(".item-actions");

      editForm.classList.add("d-none");
      textDisplay.classList.remove("d-none");
      checkInput.classList.remove("d-none");
      actions.classList.remove("d-none");
    }
  });
  socket.on("item_deleted", (data) =>
    document.getElementById(`item-${data.item_id}`)?.remove()
  );
  socket.on("item_toggled", (data) =>
    document
      .getElementById(`item-${data.item_id}`)
      ?.classList.toggle("done", data.done_status)
  );
  // --- Real-time updates for the new calendar grid ---
  socket.on("event_added", (data) => {
    // Check if we are on the calendar page
    if (document.querySelector(".calendar-grid")) {
      const event = data.event;
      const cell = document.querySelector(
        `.calendar-day[data-date="${event.date}"]`
      );

      // Ensure the cell exists and the event badge isn't already there
      if (cell && !document.getElementById(`event-${event.id}`)) {
        const eventContainer = cell.querySelector(".events-container");

        // Create the new event badge element
        const newEventBadge = document.createElement("div");

        // --- START OF FIX: Add ALL necessary attributes ---
        newEventBadge.className = "event-badge";
        newEventBadge.id = `event-${event.id}`;

        // Attributes for triggering the view modal
        newEventBadge.setAttribute("data-bs-toggle", "modal");
        newEventBadge.setAttribute("data-bs-target", "#viewEventModal");

        // Attributes to hold the event data for the modal's JavaScript
        newEventBadge.dataset.eventId = event.id;
        newEventBadge.dataset.eventTitle = event.title;
        // Use the pre-formatted 12-hour time from the server for consistency
        newEventBadge.dataset.eventTime = event.formatted_time;
        newEventBadge.dataset.eventAuthor = event.author.username;
        newEventBadge.dataset.eventAuthorId = event.author.id;

        // Set the inner HTML for display
        newEventBadge.innerHTML = `<span class="event-time">${event.time.substring(
          0,
          5
        )}</span> ${event.title}`;
        // --- END OF FIX ---

        eventContainer.appendChild(newEventBadge);
      }
    }
  });

  socket.on("event_deleted", (data) => {
    // This will work for both the old list view and the new grid view
    document.getElementById(`event-${data.event_id}`)?.remove();
  });
  socket.on("note_added", async (data) => {
    const chatContainer = document.getElementById("chat-container");
    // Echo protection: check if the bubble already exists
    if (!chatContainer || document.getElementById(`note-${data.note.id}`)) {
      return;
    }

    try {
      // Fetch the fully rendered HTML for the new bubble from our new internal route
      const response = await fetch(
        `/internal/render_bulletin_post/${data.note.id}`
      );
      if (!response.ok) return; // Don't do anything if the fetch fails

      const newBubbleHtml = await response.text();

      // Append the new bubble and scroll to the bottom
      chatContainer.insertAdjacentHTML("beforeend", newBubbleHtml);
      scrollToChatBottom();
      // Convert timestamps again to catch the new one we just added
      convertAllTimestamps(); // <-- ADD THIS LINE
    } catch (error) {
      console.error("Error fetching new bulletin post:", error);
    }
  });
  // REPLACE the existing socket.on('note_deleted', ...) with this simplified version
  socket.on("note_deleted", (data) => {
    const noteElement = document.getElementById(`note-${data.note_id}`);

    // If the deleted note was a pinned card, check if we need to hide the section
    if (noteElement && noteElement.closest("#pinned-notes-container")) {
      const pinnedContainer = document.getElementById("pinned-notes-container");
      // Check if this is the *last* child being removed
      if (pinnedContainer && pinnedContainer.children.length === 1) {
        document.getElementById("pinned-notes-section").style.display = "none";
        document.getElementById("pinned-notes-divider").classList.add("d-none");
      }
    }

    // Now, simply remove the element, wherever it was.
    if (noteElement) {
      noteElement.remove();
    }
  });
  // REPLACE the existing socket.on('note_pinned', ...) with this correct version
  socket.on("note_pinned", async (data) => {
    const { note_id, is_pinned } = data;
    const noteElement = document.getElementById(`note-${note_id}`);

    // First, remove the element from wherever it currently is.
    if (noteElement) {
      noteElement.remove();
    }

    if (is_pinned) {
      // --- LOGIC FOR PINNING A NOTE ---
      try {
        // Fetch the new 'pinned card' HTML from the server
        const response = await fetch(`/internal/render_pinned_post/${note_id}`);
        if (!response.ok) return;
        const newCardHtml = await response.text();

        const pinnedContainer = document.getElementById(
          "pinned-notes-container"
        );
        const pinnedSection = document.getElementById("pinned-notes-section");
        const pinnedDivider = document.getElementById("pinned-notes-divider");

        if (pinnedContainer) {
          // Make sure the pinned section is visible
          if (pinnedSection) pinnedSection.style.display = "block";
          if (pinnedDivider) pinnedDivider.classList.remove("d-none");

          // Add the new card to the top of the pinned list
          pinnedContainer.insertAdjacentHTML("afterbegin", newCardHtml);
        }
      } catch (error) {
        console.error("Error fetching pinned post:", error);
      }
    } else {
      // --- LOGIC FOR UNPINNING A NOTE ---
      try {
        // Fetch the 'chat bubble' HTML from the server
        const response = await fetch(
          `/internal/render_bulletin_post/${note_id}`
        );
        if (!response.ok) return;
        const newBubbleHtml = await response.text();

        const chatContainer = document.getElementById("chat-container");
        if (chatContainer) {
          // Add the bubble back to the chat and scroll down
          chatContainer.insertAdjacentHTML("beforeend", newBubbleHtml);
          scrollToChatBottom();
          convertAllTimestamps();
        }

        // Check if the pinned section is now empty and hide it if so
        const pinnedContainer = document.getElementById(
          "pinned-notes-container"
        );
        const pinnedSection = document.getElementById("pinned-notes-section");
        const pinnedDivider = document.getElementById("pinned-notes-divider");

        if (pinnedContainer && pinnedContainer.children.length === 0) {
          if (pinnedSection) pinnedSection.style.display = "none";
          if (pinnedDivider) pinnedDivider.classList.add("d-none");
        }
      } catch (error) {
        console.error("Error fetching bulletin post:", error);
      }
    }
  });
  socket.on("meal_updated", (data) => {
    if (data.sid === socket.id) return;
    const cardBody = document.querySelector(
      `.meal-card-body[data-day="${data.meal.day}"]`
    );
    if (cardBody) {
      const mainCard = cardBody.closest(".meal-day-card");
      mainCard.classList.add("meal-planned");
      updateMealCardUI(cardBody, data.meal);
    }
  });

  socket.on("meal_deleted", (data) => {
    const cardBody = document.querySelector(
      `.meal-card-body[data-day="${data.day}"]`
    );
    if (cardBody) {
      const mainCard = cardBody.closest(".meal-day-card");
      mainCard.classList.remove("meal-planned");

      cardBody.dataset.mealId = "";

      // --- THE FIX IS HERE TOO ---
      const addMealText = window.translations?.add_meal || "Add a meal";

      cardBody.innerHTML = `
        <div class="meal-empty-state">
          <i class="bi bi-plus-circle display-6 text-muted"></i>
          <p class="text-muted mt-2 mb-0">${addMealText}</p>
        </div>
      `;
    }
  });
  socket.on("chore_toggled", (data) => {
    if (data.sid === socket.id) return;

    const choreCard = document.getElementById(
      `chore-card-${data.assignment_id}`
    );
    if (choreCard) {
      const wasComplete = choreCard.classList.contains("is-complete");
      choreCard.classList.toggle("is-complete", data.is_complete);

      // Only update progress if the state actually changed
      if (wasComplete !== data.is_complete) {
        updateChoreProgress(choreCard);
      }

      sortChoreBoard(choreCard.parentElement);
    }
  });
  // Add this new function to main.js
  const sortChoreBoard = (boardElement) => {
    if (!boardElement) return;

    const cards = Array.from(boardElement.children);

    // This sort function cleverly groups completed items at the bottom.
    // It works because in JavaScript, true is 1 and false is 0.
    // Incomplete (0) will come before Complete (1).
    cards.sort((a, b) => {
      const aComplete = a.classList.contains("is-complete");
      const bComplete = b.classList.contains("is-complete");
      return aComplete - bComplete;
    });

    // Re-append the cards in the new sorted order.
    // appendChild automatically moves existing elements.
    cards.forEach((card) => boardElement.appendChild(card));
  };
  const animateCountUp = (element, start, end, total, duration = 500) => {
    // If there's no change, just set the final text and exit.
    if (start === end) {
      element.textContent = `${end} / ${total}`;
      return;
    }

    const range = end - start;
    const increment = end > start ? 1 : -1;
    const stepTime = Math.abs(Math.floor(duration / range)) || 20;

    let current = start;
    const timer = setInterval(() => {
      current += increment;
      element.textContent = `${current} / ${total}`;
      if (current === end) {
        clearInterval(timer);
      }
    }, stepTime);
  };
  const updateChoreProgress = (choreCard, isInitialLoad = false) => {
    const points = parseInt(choreCard.dataset.points, 10);
    const memberId = choreCard.dataset.memberId;
    const isNowComplete = choreCard.classList.contains("is-complete");

    // --- Update Member Progress Bar ---
    const progressContainer = document.getElementById(
      `progress-container-${memberId}`
    );
    if (progressContainer) {
      const oldCompleted = parseInt(progressContainer.dataset.completed, 10);
      const total = parseInt(progressContainer.dataset.total, 10);

      const newCompleted = isInitialLoad
        ? oldCompleted
        : isNowComplete
        ? oldCompleted + points
        : oldCompleted - points;
      progressContainer.dataset.completed = newCompleted;

      const percentage =
        total > 0 ? Math.round((newCompleted / total) * 100) : 0;

      const progressBar = document.getElementById(`progress-bar-${memberId}`);
      const progressLabel = progressBar.querySelector(".progress-label");

      progressBar.style.width = `${percentage}%`;
      // Animate the number change
      const startValue = isInitialLoad ? 0 : oldCompleted;
      animateCountUp(progressLabel, startValue, newCompleted, total);
    }

    // --- Update Family Progress Bar (if it exists) ---
    const familyProgressContainer = document.getElementById(
      "family-progress-container"
    );
    if (familyProgressContainer) {
      const oldFamilyCompleted = parseInt(
        familyProgressContainer.dataset.completed,
        10
      );
      const familyTotal = parseInt(familyProgressContainer.dataset.total, 10);

      const newFamilyCompleted = isInitialLoad
        ? oldFamilyCompleted
        : isNowComplete
        ? oldFamilyCompleted + points
        : oldFamilyCompleted - points;
      familyProgressContainer.dataset.completed = newFamilyCompleted;

      const familyPercentage =
        familyTotal > 0
          ? Math.round((newFamilyCompleted / familyTotal) * 100)
          : 0;

      const familyProgressBar = document.getElementById("family-progress-bar");
      const familyProgressLabel = document.getElementById(
        "family-progress-label"
      );

      familyProgressBar.style.width = `${familyPercentage}%`;
      // Animate the number change
      const startValue = isInitialLoad ? 0 : oldFamilyCompleted;
      const labelSuffix = ` / ${familyTotal} Points`; // Suffix for the family bar
      animateCountUp(
        familyProgressLabel,
        startValue,
        newFamilyCompleted,
        familyTotal + " Points",
        500
      );
    }
  };
  socket.on("new_activity", (data) =>
    notificationManager.handleRealtimeEvent(data.feature, data.timestamp)
  );
  function createListItemElement(item) {
    const li = document.createElement("li");
    li.className = `list-group-item d-flex justify-content-between align-items-center ${
      item.done ? "done" : ""
    }`;
    li.id = `item-${item.id}`;
    li.dataset.itemId = item.id;
    li.dataset.timestamp = item.raw_timestamp;
    li.innerHTML = `<div class="flex-grow-1 me-2"><div class="d-flex align-items-center"><span class="item-text-display flex-grow-1">${item.text}</span><button class="btn btn-sm btn-outline-secondary ms-2 item-edit-button"><i class="bi bi-pencil-square"></i></button></div><form action="/edit_item" method="POST" class="item-edit-form d-none"><input type="hidden" name="item_id" value="${item.id}"><div class="input-group"><input type="text" name="new_text" class="form-control form-control-sm" value="${item.text}"><button type="submit" class="btn btn-sm btn-outline-success">Save</button></div></form><small class="text-muted d-block">by ${item.author.username}</small></div><div><form action="/toggle_done" method="POST" class="d-inline" data-item-id="${item.id}"><input type="hidden" name="item_to_toggle" value="${item.id}"><button type="submit" class="btn btn-sm btn-success me-1">✓</button></form><form action="/delete_item" method="POST" class="d-inline confirm-delete" data-item-id="${item.id}"><input type="hidden" name="item_to_delete" value="${item.id}"><button type="submit" class="btn btn-sm btn-danger">X</button></form></div>`;
    return li;
  }
  function createEventElement(event) {
    const eventCard = document.createElement("div");
    eventCard.id = `event-${event.id}`;
    eventCard.className = "card mb-3 item-flash";
    eventCard.dataset.timestamp = event.raw_timestamp;
    let deleteButtonHTML = "";
    if (document.body.dataset.userId == event.author.id) {
      deleteButtonHTML = `<form action="/delete_event" method="POST" class="d-inline event-delete-form confirm-delete" data-event-id="${event.id}"><input type="hidden" name="event_id" value="${event.id}"><button type="submit" class="btn btn-sm btn-outline-danger" title="Delete Event"><i class="bi bi-trash"></i></button></form>`;
    }
    eventCard.innerHTML = `<div class="card-body"><div class="d-flex justify-content-between"><div><h5 class="card-title">${event.title}</h5><p class="card-subtitle mb-2 text-muted">${event.formatted_date} at ${event.formatted_time}</p><small class="text-muted">Added by ${event.author.username}</small></div><div>${deleteButtonHTML}</div></div></div>`;
    return eventCard;
  }
  function resetMealCellToEmpty(day, mealType) {
    const cellDisplay = document.getElementById(
      `meal-display-${day}-${mealType}`
    );
    const cellContainer = cellDisplay ? cellDisplay.parentElement : null;
    if (cellDisplay && cellContainer) {
      cellDisplay.innerHTML = `<p class="text-muted fst-italic">Empty</p>`;
      const textarea = cellContainer.querySelector(".add-meal-form textarea");
      if (textarea) textarea.value = "";
    }
  }
  const inviteModal = document.getElementById("inviteUserModal");
  if (inviteModal) {
    const userSelect = document.getElementById("invite-user-select");
    inviteModal.addEventListener("show.bs.modal", async () => {
      userSelect.innerHTML =
        '<option value="" disabled selected>Loading users...</option>';
      userSelect.disabled = true;
      try {
        const response = await fetch("/api/inviteable_users");
        if (!response.ok) throw new Error("Failed to load users");
        const users = await response.json();
        userSelect.innerHTML = "";
        userSelect.disabled = false;
        if (users.length > 0) {
          userSelect.innerHTML =
            '<option value="" disabled selected>Choose a user...</option>';
          users.forEach((user) => {
            const option = document.createElement("option");
            option.value = user.username;
            option.textContent = user.username;
            userSelect.appendChild(option);
          });
        } else {
          userSelect.innerHTML =
            '<option value="" disabled>No new users to invite.</option>';
        }
      } catch (error) {
        console.error("Error fetching inviteable users:", error);
        userSelect.innerHTML =
          '<option value="" disabled selected>Error loading users.</option>';
      }
    });
  }

  const scrollToChatBottom = () => {
    const chatContainer = document.getElementById("chat-container");
    if (chatContainer) {
      chatContainer.scrollTop = chatContainer.scrollHeight;
    }
  };

  // Scroll chat to bottom on initial load
  scrollToChatBottom(); // This call will now work correctly

  const handleFormSubmit = (form, event, callback) => {
    event.preventDefault();
    if (form.classList.contains("confirm-delete")) {
      formToSubmit = form;
      callbackToExecute = callback;
      confirmationModal.show();
    } else {
      executeSubmit(form, callback);
    }
  };
  const executeSubmit = async (form, callback) => {
    try {
      const formData = new FormData(form);
      const response = await fetch(form.action, {
        method: "POST",
        body: formData,
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      const data = await response.json();
      if (!response.ok) {
        if (callback) callback(form, data);
        else showToast(data.message || "An error occurred.", "danger");
        return;
      }
      if (callback) callback(form, data);
    } catch (error) {
      console.error("Error submitting form:", error);
      showToast("A network error occurred. Please try again.", "danger");
    }
  };
  if (confirmDeleteBtn) {
    confirmDeleteBtn.addEventListener("click", () => {
      if (formToSubmit) {
        executeSubmit(formToSubmit, callbackToExecute);
      }
      confirmationModal.hide();
      formToSubmit = null;
      callbackToExecute = null;
    });
  }

  const handleDeleteList = (form, data) => {
    if (data.success) {
      // Check if we are on a dedicated list page
      if (window.location.pathname.startsWith("/list/")) {
        // If so, redirect the user back to the main dashboard
        window.location.href = "/dashboard";
      }
      // The real-time "list_deleted" event will handle removing the card
      // from the DOM for any other users viewing the dashboard. The redirect
      // handles it for the current user.
    } else {
      showToast(data.message || "Failed to delete list.", "danger");
    }
  };
  // Add this new listener to main.js to handle the Edit button click
  const listPageContainer = document.querySelector(".list-group");
  if (listPageContainer) {
    listPageContainer.addEventListener("click", (e) => {
      const editButton = e.target.closest(".item-edit-button");
      if (editButton) {
        const itemCard = editButton.closest(".list-group-item");
        const textDisplay = itemCard.querySelector(".item-text-display");
        const checkInput = itemCard.querySelector(".form-check-input");
        const actions = itemCard.querySelector(".item-actions");
        const editForm = itemCard.querySelector(".item-edit-form");

        // Hide the regular view and show the edit form
        textDisplay.classList.add("d-none");
        checkInput.classList.add("d-none");
        actions.classList.add("d-none");
        editForm.classList.remove("d-none");

        // --- START: THE FIX ---
        const input = editForm.querySelector('input[name="new_text"]');
        input.focus();
        // Move the cursor to the end of the input
        input.setSelectionRange(input.value.length, input.value.length);
        // --- END: THE FIX ---
      }
    });
  }
  const handleAddItem = (form, data) => form.reset();
  const handleEditItem = (form, data) => {
    if (data.success) {
      const itemCard = form.closest(".list-group-item");
      if (itemCard) {
        // Update the visible text
        itemCard.querySelector(".item-text-display").textContent =
          data.new_text;

        // --- UI Reversal Logic ---
        const textDisplay = itemCard.querySelector(".item-text-display");
        const checkInput = itemCard.querySelector(".form-check-input");
        const actions = itemCard.querySelector(".item-actions");

        // Hide the edit form and show the regular view
        form.classList.add("d-none");
        textDisplay.classList.remove("d-none");
        checkInput.classList.remove("d-none");
        actions.classList.remove("d-none");
      }
    } else {
      showToast(data.message || "Failed to edit item.", "danger");
    }
  };
  const handleDeleteItem = (form, data) => {};
  const handleToggleItem = (form, data) => {};
  const handleAddEvent = (form, data) => form.reset();
  const handleDeleteEvent = (form, data) => {};
  const handleAddNote = (form, data) => form.reset();
  const handleDeleteNote = (form, data) => {};
  const handlePinNote = (form, data) =>
    updateNotePinStatus(form.dataset.noteId, data.is_pinned);

  // START: ADD THESE TWO NEW HANDLER FUNCTIONS
  const handleAddChore = (form, data) => {
    if (data.success) {
      showToast(data.message, "success");
      document.getElementById("no-chores-alert")?.remove();
      const choreList = document.getElementById("chore-list");
      const newChoreEl = document.createElement("div");
      newChoreEl.className =
        "list-group-item d-flex justify-content-between align-items-center";
      newChoreEl.id = `chore-${data.chore.id}`;
      newChoreEl.innerHTML = `
        <div>
            <span>${data.chore.name}</span>
            <span class="badge bg-secondary rounded-pill ms-2">${data.chore.points} points</span>
        </div>
        <form action="/chores/delete" method="POST" class="delete-chore-form d-inline confirm-delete" style="margin: 0">
            <input type="hidden" name="chore_id" value="${data.chore.id}" />
            <button type="submit" class="btn btn-sm btn-outline-danger" title="Delete Chore"><i class="bi bi-trash"></i></button>
        </form>
      `;
      choreList.appendChild(newChoreEl);
      form.reset();
      form.querySelector('input[name="chore_name"]').focus();
    } else {
      showToast(data.message, "danger");
    }
  };

  const handleDeleteChore = (form, data) => {
    if (data.success) {
      showToast(data.message || "Chore deleted.", "info");
      form.closest(".list-group-item")?.remove();
    } else {
      showToast(data.message, "danger");
    }
  };
  // END: ADD THESE TWO NEW HANDLER FUNCTIONS

  const handleInviteUser = (form, data) => {
    if (data.success) {
      showToast(data.message, "success");
      const modal = bootstrap.Modal.getInstance(
        document.getElementById("inviteUserModal")
      );
      modal.hide();
      form.reset();
    } else {
      showToast(data.message, "warning");
    }
  };

  // Place this with the other handler functions
  // Replace the existing handleAddVaultEntry function
  const handleAddVaultEntry = (form, data) => {
    if (data.success) {
      const modalElement = form.closest(".modal");
      const modalInstance = bootstrap.Modal.getInstance(modalElement);
      if (modalInstance) {
        modalInstance.hide();
      }
      form.reset();

      showToast(data.message, "success");

      // Remove the "empty" card if it exists
      document.getElementById("empty-vault-card")?.remove();

      const newCategoryName = data.entry.category;
      const accordion = document.getElementById("vaultAccordion");
      const categoryId =
        "category-" + newCategoryName.replace(/\s+/g, "-").toLowerCase();

      let listGroup = document.getElementById(categoryId);
      let collapseElement;

      if (!listGroup) {
        const collapseId =
          "collapse-" + newCategoryName.replace(/\s+/g, "-").toLowerCase();
        const headingId =
          "heading-" + newCategoryName.replace(/\s+/g, "-").toLowerCase();
        const newAccordionItem = document.createElement("div");
        newAccordionItem.className = "accordion-item";
        newAccordionItem.innerHTML = `
                <h2 class="accordion-header" id="${headingId}">
                    <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#${collapseId}" aria-expanded="false" aria-controls="${collapseId}">
                        ${newCategoryName}
                    </button>
                </h2>
                <div id="${collapseId}" class="accordion-collapse collapse" aria-labelledby="${headingId}" data-bs-parent="#vaultAccordion">
                    <div class="list-group list-group-flush" id="${categoryId}">
                    </div>
                </div>
            `;
        accordion.appendChild(newAccordionItem);
        listGroup = newAccordionItem.querySelector(".list-group-flush");
        collapseElement = newAccordionItem.querySelector(".accordion-collapse");
      } else {
        collapseElement = listGroup.closest(".accordion-collapse");
      }

      listGroup.insertAdjacentHTML("beforeend", data.entry_html);

      const modalContainer = document.getElementById("modal-container");
      modalContainer.insertAdjacentHTML("beforeend", data.edit_modal_html);

      // Ensure the accordion section is open
      if (collapseElement) {
        const bsCollapse = new bootstrap.Collapse(collapseElement, {
          toggle: false,
        });
        bsCollapse.show();
      }
    } else {
      showToast(data.message || "Failed to add entry.", "danger");
    }
  };

  // Replace the existing handleEditVaultEntry function with this one
  const handleEditVaultEntry = (form, data) => {
    if (data.success) {
      const modalElement = form.closest(".modal");
      const modalInstance = bootstrap.Modal.getInstance(modalElement);
      if (modalInstance) {
        modalInstance.hide();
      }
      showToast(data.message, "success");

      const entryData = data.entry;
      const existingEntryElement = document.getElementById(
        `vault-entry-${entryData.id}`
      );

      if (existingEntryElement) {
        if (entryData.category === entryData.original_category) {
          existingEntryElement.outerHTML = data.entry_html;
        } else {
          const originalListGroup = existingEntryElement.parentElement;
          existingEntryElement.remove();

          const newCategoryName = entryData.category;
          const accordion = document.getElementById("vaultAccordion");
          const categoryId =
            "category-" + newCategoryName.replace(/\s+/g, "-").toLowerCase();
          let listGroup = document.getElementById(categoryId);
          let collapseElement;

          if (!listGroup) {
            const collapseId =
              "collapse-" + newCategoryName.replace(/\s+/g, "-").toLowerCase();
            const headingId =
              "heading-" + newCategoryName.replace(/\s+/g, "-").toLowerCase();
            const newAccordionItem = document.createElement("div");
            newAccordionItem.className = "accordion-item";
            newAccordionItem.innerHTML = `
                        <h2 class="accordion-header" id="${headingId}">
                            <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#${collapseId}" aria-expanded="false" aria-controls="${collapseId}">
                                ${newCategoryName}
                            </button>
                        </h2>
                        <div id="${collapseId}" class="accordion-collapse collapse" data-bs-parent="#vaultAccordion">
                            <div class="list-group list-group-flush" id="${categoryId}"></div>
                        </div>
                    `;
            accordion.appendChild(newAccordionItem);
            listGroup = newAccordionItem.querySelector(".list-group-flush");
            collapseElement = newAccordionItem.querySelector(
              ".accordion-collapse"
            );
          } else {
            collapseElement = listGroup.closest(".accordion-collapse");
          }
          listGroup.insertAdjacentHTML("beforeend", data.entry_html);

          if (originalListGroup && originalListGroup.children.length === 0) {
            const accordionItem = originalListGroup.closest(".accordion-item");
            if (accordionItem) {
              accordionItem.remove();
            }
          }

          // Ensure the new accordion section is open
          if (collapseElement) {
            const bsCollapse = new bootstrap.Collapse(collapseElement, {
              toggle: false,
            });
            bsCollapse.show();
          }
        }
      }
    } else {
      showToast(data.message || "Failed to update entry.", "danger");
    }
  };

  // START: ADD NEW HANDLER FUNCTION
  // Replace the entire function with this new version
  const handleDeleteVaultEntry = (form, data) => {
    if (data.success) {
      showToast(data.message, "info");

      const entryElement = form.closest(".list-group-item");
      if (entryElement) {
        // Find the parent container for all items in this category
        const listGroup = entryElement.parentElement;

        // Remove the specific item element
        entryElement.remove();

        // Check if the list group is now empty
        if (listGroup && listGroup.children.length === 0) {
          // If it's empty, find the top-level accordion item and remove it
          const accordionItem = listGroup.closest(".accordion-item");
          if (accordionItem) {
            accordionItem.remove();
          }
        }
      }
    } else {
      showToast(data.message || "Failed to delete entry.", "danger");
    }
  };
  // END: ADD NEW HANDLER FUNCTION

  const handleDeleteMealOptimistic = (form, data) => {
    if (data.success) {
      const deletedId = form.querySelector('input[name="meal_id"]').value;

      // 1. Close modal
      const modalElement = document.getElementById("mealModal");
      const modalInstance = bootstrap.Modal.getInstance(modalElement);
      if (modalInstance) modalInstance.hide();

      // 2. Reset form
      document.getElementById("meal-form").reset();
      const previewContainer = document.getElementById(
        "meal-notes-links-preview"
      );
      if (previewContainer) previewContainer.classList.add("d-none");

      // 3. Update UI Card
      const cardBody = document.querySelector(
        `.meal-card-body[data-meal-id="${deletedId}"]`
      );
      if (cardBody) {
        const mainCard = cardBody.closest(".meal-day-card");
        mainCard.classList.remove("meal-planned");
        cardBody.dataset.mealId = "";

        // --- THE FIX IS HERE ---
        // We use the variable we defined in the HTML, falling back to English if missing
        const addMealText = window.translations?.add_meal || "Add a meal";

        cardBody.innerHTML = `
            <div class="meal-empty-state">
              <i class="bi bi-plus-circle display-6 text-muted"></i>
              <p class="text-muted mt-2 mb-0">${addMealText}</p>
            </div>
        `;
      }

      // 4. Clean Data
      if (window.mealPlanData) {
        Object.keys(window.mealPlanData).forEach((key) => {
          const meal = window.mealPlanData[key];
          if (meal && meal.id == deletedId) {
            window.mealPlanData[key] = null;
          }
        });
      }

      showToast("Meal removed successfully.", "success");
    } else {
      showToast(data.message || "Failed to remove meal.", "danger");
    }
  };

  // =======================================================================
  // START: NEW UNIFIED AND DELEGATED EVENT LISTENER
  // =======================================================================
  document.body.addEventListener("submit", (event) => {
    // Find the form that was submitted
    const form = event.target.closest("form");
    if (!form) return;

    const handleAddEventGrid = (form, data) => {
      if (data.success) {
        form.reset();
        const modal = bootstrap.Modal.getInstance(
          document.getElementById("addEventModal")
        );
        modal.hide();
        // Real-time event 'event_added' will handle updating the UI for everyone
      } else {
        showToast(data.message || "Failed to add event.", "danger");
      }
    };

    const handleEditEventGrid = (form, data) => {
      if (data.success) {
        form.reset();
        const modal = bootstrap.Modal.getInstance(
          document.getElementById("addEventModal")
        );
        modal.hide();
        // The 'event_updated' socket event will handle the UI update
      } else {
        showToast(data.message || "Failed to update event.", "danger");
      }
    };

    // A map of form selectors to their specific handler functions
    const formActions = {
      // List Forms
      ".create-list-form": (form, data) => {
        if (data.success) form.reset();
      },
      'form[action="/delete_list"]': handleDeleteList,
      ".item-add-form": handleAddItem,
      ".item-edit-form": handleEditItem,
      'form[action="/delete_item"]': handleDeleteItem,
      'form[action="/toggle_done"]': handleToggleItem,
      // Invite Form
      ".invite-user-form": handleInviteUser,
      // Note Forms
      ".note-add-form": handleAddNote,
      ".note-delete-form": handleDeleteNote,
      // CORRECT THIS LINE:
      ".note-pin-form": (form, data) => {}, // The socket event handles the UI update, so this does nothing.
      // Event Forms
      "#add-event-form": handleAddEventGrid, // Use the new handler for the grid
      'form[action^="/edit_event/"]': handleEditEventGrid,
      ".event-delete-form": handleDeleteEvent,
      // Meal Forms
      "#delete-meal-form": handleDeleteMealOptimistic,

      // ===============================================
      // START: THE FIX
      // ===============================================
      // Chore Management Forms
      "#add-chore-form": handleAddChore,
      ".delete-chore-form": handleDeleteChore,
      // ===============================================
      // END: THE FIX
      // ===============================================

      // Vault Forms
      'form[action="/vault/add"]': handleAddVaultEntry,
      'form[action^="/vault/edit/"]': handleEditVaultEntry,
      'form[action="/vault/delete"]': handleDeleteVaultEntry,
    };

    // Loop through the map to find a match
    for (const selector in formActions) {
      if (form.matches(selector)) {
        // We found a match! Call the main gatekeeper function.
        handleFormSubmit(form, event, formActions[selector]);
        return; // Stop after we've found and handled the correct form
      }
    }
  });

  // =======================================================================
  // START: CONSOLIDATED CALENDAR LOGIC (DESKTOP & MODALS)
  // =======================================================================

  const addEventModalElement = document.getElementById("addEventModal");
  const viewEventModalElement = document.getElementById("viewEventModal");

  // This check ensures none of this code runs if we're not on the calendar page.
  if (addEventModalElement && viewEventModalElement) {
    // --- Get all modal-related elements ONCE ---
    const addEventModal = new bootstrap.Modal(addEventModalElement);
    const dateInput = document.getElementById("event-date-input");
    const modalTitle = document.getElementById("addEventModalLabel");
    const addEventForm = document.getElementById("add-event-form");
    const addEventSubmitBtn = addEventForm.querySelector(
      'button[type="submit"]'
    );

    // --- ADD THESE FOUR LINES ---
    const eventHourSelect = document.getElementById("event-hour");
    const eventMinuteSelect = document.getElementById("event-minute");
    const hiddenTimeInput = document.getElementById("event-time-hidden");
    const timeSelectGroup = document.getElementById("addEventModal"); // The whole modal
    // --- END OF ADDITION ---

    // --- NEW LOGIC for managing the time dropdowns ---
    if (timeSelectGroup) {
      // Function to update the hidden input
      const updateHiddenTime = () => {
        const hour = eventHourSelect.value;
        const minute = eventMinuteSelect.value;
        hiddenTimeInput.value = `${hour}:${minute}`;
      };

      // Add listeners to both dropdowns
      eventHourSelect.addEventListener("change", updateHiddenTime);
      eventMinuteSelect.addEventListener("change", updateHiddenTime);

      // Set an initial value when the page loads
      updateHiddenTime();
    }
    // --- END OF NEW LOGIC ---

    const viewEventModal = new bootstrap.Modal(viewEventModalElement);
    const titleEl = document.getElementById("view-event-title");
    const timeEl = document.getElementById("view-event-time");
    const authorEl = document.getElementById("view-event-author");
    const deleteBtn = document.getElementById("delete-event-btn");
    const editBtn = document.getElementById("edit-event-btn");
    const authorActions = document.getElementById("event-author-actions");

    // --- Logic for the ADD/EDIT Modal ---

    // 1. Dedicated listener for clicks on the DESKTOP calendar grid to ADD an event.
    const calendarGrid = document.querySelector(".calendar-grid");
    if (calendarGrid) {
      calendarGrid.addEventListener("click", (e) => {
        const cell = e.target.closest(".calendar-day");
        // This makes sure we don't trigger the modal when clicking an existing event badge.
        const badge = e.target.closest(".event-badge");

        if (cell && !badge && cell.dataset.date) {
          // Explicitly set up the modal for a clean "Add" operation.
          addEventForm.action = "/add_event";
          modalTitle.textContent = `Add Event for ${cell.dataset.date}`;
          addEventSubmitBtn.textContent = "Add Event";
          dateInput.value = cell.dataset.date;
          addEventForm.reset(); // Reset form fields
          addEventModal.show();
        }
      });
    }

    // 2. Reset the Add/Edit modal to its "Add" state ONLY when it's hidden.
    // This is the safest way to clean up after both adding and editing.
    addEventModalElement.addEventListener("hidden.bs.modal", () => {
      addEventForm.action = "/add_event";
      modalTitle.textContent = "Add Event";
      addEventSubmitBtn.textContent = "Add Event";
      addEventForm.reset();
    });

    // --- Logic for the VIEW Modal ---

    // 1. Populate the VIEW modal with data from the clicked event badge/item.
    viewEventModalElement.addEventListener("show.bs.modal", (event) => {
      const triggerElement = event.relatedTarget;
      if (!triggerElement) return;

      const dataset = triggerElement.dataset;
      viewEventModalElement.dataset.eventId = dataset.eventId;
      viewEventModalElement.dataset.eventTitle = dataset.eventTitle;
      viewEventModalElement.dataset.eventTime = dataset.eventTime;
      viewEventModalElement.dataset.eventAuthor = dataset.eventAuthor;
      viewEventModalElement.dataset.eventAuthorId = dataset.eventAuthorId;

      // For desktop, date is on parent. For mobile, it's not, so we find it in our state.
      if (triggerElement.closest(".calendar-day")) {
        viewEventModalElement.dataset.eventDate =
          triggerElement.closest(".calendar-day").dataset.date;
      } else if (window.calendarEvents) {
        const eventState = window.calendarEvents.find(
          (e) => e.eventId == dataset.eventId
        );
        if (eventState) {
          viewEventModalElement.dataset.eventDate = eventState.date;
        }
      }

      titleEl.textContent = dataset.eventTitle;
      timeEl.textContent = dataset.eventTime;
      authorEl.textContent = dataset.eventAuthor;

      const currentUserId = document.body.dataset.userId;
      authorActions.style.display =
        currentUserId === dataset.eventAuthorId ? "block" : "none";
    });

    // 2. Handle the "Delete Event" button click inside the VIEW modal.
    deleteBtn.addEventListener("click", () => {
      const formToTrigger = document.querySelector(".event-delete-form");
      const idInput = document.getElementById("delete-event-id-input");
      const eventId = viewEventModalElement.dataset.eventId;

      if (formToTrigger && idInput && eventId) {
        idInput.value = eventId;
        viewEventModal.hide();
        formToTrigger.dispatchEvent(
          new Event("submit", { bubbles: true, cancelable: true })
        );
      }
    });

    // 3. Handle the "Edit Event" button click inside the VIEW modal.
    editBtn.addEventListener("click", () => {
      const dataset = viewEventModalElement.dataset;

      // Get the 24-hour time string (e.g., "14:30")
      const time24h = new Date("1970-01-01 " + dataset.eventTime)
        .toTimeString()
        .substring(0, 5);

      // --- THIS IS THE NEW LOGIC ---
      // Split the time into hour and minute parts
      const [hour, minute] = time24h.split(":");

      // Pre-fill the Add/Edit modal's form
      addEventForm.querySelector("#event-title").value = dataset.eventTitle;
      dateInput.value = dataset.eventDate;

      // Set the values of our new dropdowns
      eventHourSelect.value = hour;
      eventMinuteSelect.value = minute;

      // Manually update the hidden input to be sure it's correct
      hiddenTimeInput.value = time24h;
      // --- END OF NEW LOGIC ---

      // Change the form's action and the modal's title/button text
      addEventForm.action = `/edit_event/${dataset.eventId}`;
      modalTitle.textContent = "Edit Event";
      addEventSubmitBtn.textContent = "Update Event";

      viewEventModal.hide();
      addEventModal.show();
    });
  }
  // =======================================================================
  // END: CONSOLIDATED CALENDAR LOGIC
  // =======================================================================

  // --- MEAL PLANNER MODAL LOGIC ---
  const mealModalElement = document.getElementById("mealModal");
  if (mealModalElement) {
    const mealModal = new bootstrap.Modal(mealModalElement);
    const mealModalLabel = document.getElementById("mealModalLabel");
    const mealDescriptionInput = document.getElementById(
      "meal-description-input"
    );
    const mealDayInput = document.getElementById("meal-day-input");
    const mealNotesInput = document.getElementById("meal-notes-input");

    // Forms and buttons
    const mealForm = document.getElementById("meal-form");
    const deleteMealButton = document.getElementById("delete-meal-button");
    const deleteMealForm = document.getElementById("delete-meal-form");
    const deleteMealIdInput = document.getElementById("delete-meal-id-input");

    let currentCardBody = null; // Variable to keep track of the active card

    // Helper function to update the main card UI
    const updateMealCardUI = (cardBody, meal) => {
      cardBody.dataset.mealId = meal.id;

      let notesIndicatorHTML = "";
      if (meal.notes && meal.notes.trim() !== "") {
        notesIndicatorHTML = `
                <div class="meal-notes-indicator">
                    <i class="bi bi-info-circle-fill"></i>
                </div>`;
      }

      cardBody.innerHTML = `
            <p class="fs-5 mb-1 meal-description">${meal.description}</p>
            ${notesIndicatorHTML}`;
    };

    // 1. Populate modal when it's opened
    mealModalElement.addEventListener("show.bs.modal", (event) => {
      mealModalElement._currentCardBody = event.relatedTarget;
      currentCardBody = event.relatedTarget;
      const day = currentCardBody.dataset.day;
      const mealId = currentCardBody.dataset.mealId;

      // Use the global window object we created to get full meal data
      const meal = window.mealPlanData[day] || {};

      const description = meal.description || "";
      const notes = meal.notes || "";
      const notes_html = meal.notes_html || "";

      // --- ADD THESE LINES ---
      const notesHtml = meal.notes_html || "";
      const previewContainer = document.getElementById(
        "meal-notes-links-preview"
      );
      const previewContent = document.getElementById("meal-notes-content");

      // Check if there are actual links or text to show
      if (notesHtml && notesHtml.trim() !== "") {
        previewContent.innerHTML = notesHtml;
        previewContainer.classList.remove("d-none");
      } else {
        previewContainer.classList.add("d-none");
      }
      // -----------------------

      // Set modal title and form inputs
      mealModalLabel.textContent = mealId
        ? `Edit ${day}'s Dinner`
        : `Add ${day}'s Dinner`;
      mealDayInput.value = day;
      mealDescriptionInput.value = description;
      mealNotesInput.value = notes; // Populate the editable notes textarea

      // Control visibility of the delete button
      if (mealId) {
        deleteMealIdInput.value = mealId;
        deleteMealButton.style.display = "block";
      } else {
        deleteMealIdInput.value = "";
        deleteMealButton.style.display = "none";
      }
    });

    // 2. Handle the Save/Edit form submission
    mealForm.addEventListener("submit", (e) => {
      e.preventDefault();

      // Get all form values, including the new hidden one
      const day = mealDayInput.value;
      const description = mealDescriptionInput.value;
      const notes = mealNotesInput.value;
      const week_of = document.getElementById("meal-week-of-input").value; // <-- ADD THIS LINE

      // Optimistic UI Update (no changes here)
      const mainCard = currentCardBody.closest(".meal-day-card");
      mainCard.classList.add("meal-planned");
      updateMealCardUI(currentCardBody, {
        id: "",
        description: description,
        notes: notes,
      });
      mealModal.hide();

      // Emit event to server with a callback
      socket.emit(
        "save_meal",
        {
          day: day,
          description: description,
          notes: notes,
          week_of: week_of,
        },
        (meal_data) => {
          if (meal_data) {
            // Finalize UI with correct data from server
            updateMealCardUI(currentCardBody, meal_data);

            // Update the global data object so the modal has fresh info next time
            // This ensures the 'notes_html' is saved to our local cache
            window.mealPlanData[day] = meal_data;
          } else {
            showToast("Failed to save meal. Please refresh.", "danger");
          }
        }
      );
    });

    // 3. Handle the "Remove" button click to trigger confirmation
    deleteMealButton.addEventListener("click", () => {
      formToSubmit = deleteMealForm;
      callbackToExecute = handleDeleteMealOptimistic;
      confirmationModal.show();
    });

    // 4. Handle the successful deletion AFTER confirmation

    // This is a reminder to ensure this line exists in your main delegated listener's formActions map
    // formActions['#delete-meal-form'] = handleDeleteMealOptimistic;
  }

  const updateMealCardUI = (cardBody, meal) => {
    cardBody.dataset.mealId = meal.id;

    let notesIndicatorHTML = "";
    if (meal.notes && meal.notes.trim() !== "") {
      notesIndicatorHTML = `
                <div class="meal-notes-indicator">
                    <i class="bi bi-card-text"></i>
                </div>`;
    }

    cardBody.innerHTML = `
            <p class="fs-5 mb-1 meal-description">${meal.description}</p>
            ${notesIndicatorHTML}`;
  };

  // =======================================================================
  // END: NEW UNIFIED AND DELEGATED EVENT LISTENER
  // =======================================================================

  notificationManager.checkAllOnLoad();
  notificationManager.clearCurrentPageNotification();
  // This listener for the "Generate Chores" button is a special case.
  // It has its own AJAX logic and doesn't need the confirmation modal,
  // so it remains separate from the delegated listener.
  // This listener handles the "Generate Chores" button click for both desktop and mobile.
  document.querySelectorAll(".generate-chores-btn").forEach((button) => {
    button.addEventListener("click", function (event) {
      event.preventDefault();

      // Disable both buttons to prevent double-clicks
      document
        .querySelectorAll(".generate-chores-btn")
        .forEach((btn) => (btn.disabled = true));

      // Show a loading state on the specific button that was clicked
      const originalText = this.innerHTML;
      this.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Generating...`;

      fetch("/chores/generate", {
        method: "POST",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
        },
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.success) {
            showToast(data.message, "success");
            // Reload the page after a short delay to show the new assignments
            setTimeout(() => window.location.reload(), 1500);
          } else {
            showToast(data.message || "An error occurred.", "danger");
            // Restore buttons on failure
            document.querySelectorAll(".generate-chores-btn").forEach((btn) => {
              btn.innerHTML = originalText;
              btn.disabled = false;
            });
          }
        })
        .catch((error) => {
          console.error("Error generating chores:", error);
          showToast("A network error occurred.", "danger");
          // Restore buttons on network error
          document.querySelectorAll(".generate-chores-btn").forEach((btn) => {
            btn.innerHTML = originalText;
            btn.disabled = false;
          });
        });
    });
  });

  // This listener handles checkbox changes on the chore list, not form submissions.
  // It can remain as is.
  const choreListContainer = document.getElementById("chore-list-container");
  if (choreListContainer) {
    choreListContainer.addEventListener("click", (e) => {
      const completionButton = e.target.closest(".completion-button");

      if (
        completionButton &&
        !completionButton.classList.contains("is-disabled")
      ) {
        const choreCard = completionButton.closest(".chore-card");

        // Optimistic UI Update
        choreCard.classList.toggle("is-complete");
        updateChoreProgress(choreCard); // Update progress immediately
        sortChoreBoard(choreCard.parentElement);

        socket.emit("toggle_chore", {
          assignment_id: choreCard.dataset.assignmentId,
        });
      }
    });
  }
  // --- START: ADD THIS NEW CODE FOR CHORE HISTORY AJAX ---
  const historyTabPane = document.getElementById("history");
  if (historyTabPane) {
    historyTabPane.addEventListener("click", async (e) => {
      const link = e.target.closest(".history-nav-link");
      if (!link) return; // Exit if the click wasn't on a nav link
      e.preventDefault();

      const url = link.href;
      link.classList.add("disabled"); // Disable button to prevent double-clicks

      try {
        const response = await fetch(url);
        if (!response.ok) throw new Error("Network response was not ok");

        const data = await response.json();
        if (data.success) {
          // Target the specific containers within the History tab
          const gridContainer = document.getElementById(
            "history-grid-container"
          );
          const navContainer = document.getElementById("chore-history-nav");
          const weekDisplay = document.getElementById("history-week-display");

          if (gridContainer) gridContainer.innerHTML = data.grid_html;
          if (navContainer) navContainer.innerHTML = data.nav_html;
          if (weekDisplay)
            weekDisplay.textContent = `Week of ${data.week_display}`;

          // Update the URL in the browser bar for better UX
          window.history.pushState(
            {},
            "",
            `/chore_history/${url.split("/").pop()}`
          );
        } else {
          showToast(data.error || "Failed to load history.", "danger");
        }
      } catch (error) {
        console.error("Error fetching chore history:", error);
        showToast("An error occurred while loading history.", "danger");
      } finally {
        link.classList.remove("disabled"); // Re-enable the button
      }
    });
  }
  // --- END: ADD THIS NEW CODE ---
  // --- START: ADD THIS NEW CODE TO FIX THE URL ON TAB CHANGE ---
  const choresTabContainer = document.getElementById("choresTab");
  if (choresTabContainer) {
    choresTabContainer.addEventListener("show.bs.tab", (event) => {
      // The event.target is the tab that is ABOUT to be shown.
      const newTabId = event.target.id;

      // If the user is navigating to any tab OTHER THAN the history tab...
      if (newTabId !== "history-tab") {
        // ...and if the URL is not already the base '/chores' URL...
        if (window.location.pathname !== "/chores") {
          // ...then reset the URL to '/chores' without reloading the page.
          // We use replaceState so it doesn't clutter the browser history.
          window.history.replaceState(null, "", "/chores");
        }
      }
    });
  }
  // --- END: ADD THIS NEW CODE ---
  // --- Trigger Progress Bar Animation on Page Load ---
  document.querySelectorAll(".chore-card[data-member-id]").forEach((card) => {
    // We only need to run this once per member, so we use a check.
    const memberId = card.dataset.memberId;
    const progressContainer = document.getElementById(
      `progress-container-${memberId}`
    );
    if (progressContainer && !progressContainer.dataset.animated) {
      // Create a dummy card object to pass to the update function
      const dummyCard = {
        dataset: { points: 0, memberId: memberId },
        classList: { contains: () => false },
      };
      updateChoreProgress(dummyCard, true);
      progressContainer.dataset.animated = "true"; // Mark as animated
    }
  });

  // Also animate the main family progress bar on load
  const familyProgressContainer = document.getElementById(
    "family-progress-container"
  );
  if (familyProgressContainer && !familyProgressContainer.dataset.animated) {
    const dummyCard = {
      dataset: { points: 0, memberId: "family" },
      classList: { contains: () => false },
    };
    updateChoreProgress(dummyCard, true);
    familyProgressContainer.dataset.animated = "true";
  }

  // Add this entire block to the end of your DOMContentLoaded listener in main.js

  // =======================================================
  // LOGIC FOR THE FOCUSED LIST VIEW PAGE (/list/<id>)
  // =======================================================
  if (window.location.pathname.startsWith("/list/")) {
    const uncompletedListEl = document.querySelector("#items-list");
    const completedListEl = document.querySelector("#completed-items-list");
    const completedContainer = document.getElementById(
      "completed-items-container"
    );

    const createItemElement = (item) => {
      const div = document.createElement("div");
      div.className = "list-group-item";
      div.id = `item-${item.id}`;
      div.dataset.itemId = item.id;

      div.innerHTML = `
            <input class="form-check-input item-toggle-checkbox" type="checkbox" value="" 
                   id="check-${item.id}" data-item-id="${item.id}" 
                   ${item.done ? "checked" : ""}>
            
            <label class="item-text-display flex-grow-1" for="check-${
              item.id
            }">${item.text}</label>
            
            <div class="item-actions ms-auto">
                <button class="btn btn-sm border-0 p-1 item-edit-button" title="Edit">
                    <i class="bi bi-pencil"></i>
                </button>
                <form action="/delete_item" method="POST" class="d-inline confirm-delete mb-0" data-item-id="${
                  item.id
                }">
                    <input type="hidden" name="item_to_delete" value="${
                      item.id
                    }">
                    <button type="submit" class="btn btn-sm border-0 p-1" title="Delete">
                        <i class="bi bi-trash"></i>
                    </button>
                </form>
            </div>
            
            <form action="/edit_item" method="POST" class="item-edit-form d-none w-100">
                <input type="hidden" name="item_id" value="${item.id}">
                <div class="input-group">
                    <input type="text" name="new_text" class="form-control form-control-sm" value="${
                      item.text
                    }">
                    <button type="submit" class="btn btn-sm btn-outline-success">Save</button>
                </div>
            </form>
        `;
      return div;
    };

    const renderItems = (items) => {
      uncompletedListEl.innerHTML = "";
      completedListEl.innerHTML = "";
      let completedCount = 0;
      items.forEach((item) => {
        const itemEl = createItemElement(item);
        if (item.done) {
          completedListEl.appendChild(itemEl);
          completedCount++;
        } else {
          uncompletedListEl.appendChild(itemEl);
        }
      });
      // Hide completed section if there are no completed items
      completedContainer.style.display = completedCount > 0 ? "block" : "none";
    };

    // Handle item toggling (moving between lists)
    document.body.addEventListener("change", (e) => {
      if (e.target.matches(".item-toggle-checkbox")) {
        const checkbox = e.target;
        const itemId = checkbox.dataset.itemId;
        const card = checkbox.closest(".list-group-item");

        if (checkbox.checked) {
          completedListEl.prepend(card);
        } else {
          uncompletedListEl.prepend(card);
        }

        // Update visibility of completed section
        completedContainer.style.display =
          completedListEl.children.length > 0 ? "block" : "none";

        socket.emit("toggle_done", { item_to_toggle: itemId });
      }
    });

    // Socket.IO event handlers specific to this page
    socket.on("item_added", (data) => {
      if (uncompletedListEl.dataset.listId == data.list_id) {
        if (!document.getElementById(`item-${data.item.id}`)) {
          const newItemEl = createItemElement(data.item);
          uncompletedListEl.prepend(newItemEl);
        }
      }
    });

    socket.on("item_toggled", (data) => {
      if (uncompletedListEl.dataset.listId == data.list_id) {
        const itemEl = document.getElementById(`item-${data.item_id}`);
        if (itemEl) {
          const checkbox = itemEl.querySelector(".item-toggle-checkbox");
          checkbox.checked = data.done_status;
          // Manually dispatch a change event to trigger our move logic
          checkbox.dispatchEvent(new Event("change"));
        }
      }
    });

    // Initial render
    if (window.initialItems) {
      renderItems(window.initialItems);
    }
  }

  socket.on("event_updated", (data) => {
    const event = data.event;
    const badge = document.getElementById(`event-${event.id}`);
    if (badge) {
      // Update the visible text
      badge.innerHTML = `<span class="event-time">${event.time.substring(
        0,
        5
      )}</span> ${event.title}`;

      // CRUCIAL: Also update the data attributes for the view modal
      badge.dataset.eventTitle = event.title;
      badge.dataset.eventTime = event.formatted_time;
    }
  });

  // Hide the mobile "Add Item" modal after form submission
  const addItemModalEl = document.getElementById("addItemModal");
  if (addItemModalEl) {
    addItemModalEl.addEventListener("submit", () => {
      const modal = bootstrap.Modal.getInstance(addItemModalEl);
      if (modal) {
        modal.hide();
      }
    });
  }

  // Update the handler for creating a list to close its modal
  const createListModalEl = document.getElementById("createListModal");
  if (createListModalEl) {
    createListModalEl.addEventListener("submit", () => {
      const modal = bootstrap.Modal.getInstance(createListModalEl);
      if (modal) {
        modal.hide();
      }
    });
  }
  // ADD THIS CODE BLOCK TO main.js

  // --- START: NEW ROBUST PASSWORD TOGGLE LOGIC ---
  document.body.addEventListener("click", function (event) {
    // Find the button that was actually clicked by checking for our new class
    const toggleButton = event.target.closest(".toggle-password-button");

    // If the click was not on a toggle button, do nothing.
    if (!toggleButton) {
      return;
    }

    // Get the ID of the target input from the button's data-target attribute
    const targetInputSelector = toggleButton.dataset.target;
    if (!targetInputSelector) {
      return;
    }

    // Find the corresponding password input field using that ID
    const passwordInput = document.querySelector(targetInputSelector);
    if (!passwordInput) {
      return;
    }

    // Toggle the input type between 'password' and 'text'
    const type =
      passwordInput.getAttribute("type") === "password" ? "text" : "password";
    passwordInput.setAttribute("type", type);

    // Toggle the icon on the button that was clicked
    const icon = toggleButton.querySelector("i");
    if (icon) {
      icon.classList.toggle("bi-eye-slash-fill");
      icon.classList.toggle("bi-eye-fill");
    }
  });
  // --- END: NEW ROBUST PASSWORD TOGGLE LOGIC ---

  // ADD THIS SECOND CODE BLOCK TO main.js

  // --- START: NEW REGISTER FORM VALIDATION ---
  const registerForm = document.getElementById("register-form");
  if (registerForm) {
    // Find the error message container we just added to the HTML
    const errorDiv = document.getElementById("password-match-error");

    registerForm.addEventListener("submit", function (event) {
      const password = registerForm.querySelector(
        "#register-password-input"
      ).value;
      const confirmPassword = registerForm.querySelector(
        "#confirm-password-input"
      ).value;

      if (password !== confirmPassword) {
        // Passwords do NOT match:
        // 1. Prevent the form from submitting
        event.preventDefault();
        // 2. Show the error message by removing the 'd-none' class
        errorDiv.classList.remove("d-none");
      } else {
        // Passwords DO match:
        // 1. Ensure the error message is hidden
        errorDiv.classList.add("d-none");
      }
    });
  }
  // =======================================================
  // START: NEW MOBILE CALENDAR & AGENDA VIEW LOGIC
  // =======================================================
  const mobileCalendarContainer = document.getElementById(
    "mobile-month-navigator"
  );
  if (mobileCalendarContainer) {
    // --- A. HELPER FUNCTIONS ---

    // This array will be our single source of truth for the mobile view's state.
    window.calendarEvents = [];

    /**
     * Parses all event data from the desktop grid ONCE on page load to populate our state.
     */
    const initializeEventsState = () => {
      calendarEvents = []; // Reset the array
      document.querySelectorAll(".event-badge").forEach((badge) => {
        const eventData = { ...badge.dataset };
        eventData.date = badge.closest(".calendar-day").dataset.date;
        calendarEvents.push(eventData);
      });
    };

    /**
     * Renders the compact, interactive month navigator.
     * @param {Array} allEvents - The complete list of events for the month.
     * @param {string} selectedDateStr - The currently selected date string ('YYYY-MM-DD').
     * @param {string} todayDateStr - Today's date string ('YYYY-MM-DD').
     * @param {string} currentMonthStr - The current month being viewed ('YYYY-MM').
     */
    const renderMobileMonthNavigator = (
      selectedDateStr,
      todayDateStr,
      currentMonthStr
    ) => {
      const navigator = document.getElementById("mobile-month-navigator");
      navigator.dataset.selectedDate = selectedDateStr; // Store state
      let html =
        '<div class="mobile-cal-header">Mo</div><div class="mobile-cal-header">Tu</div><div class="mobile-cal-header">We</div><div class="mobile-cal-header">Th</div><div class="mobile-cal-header">Fr</div><div class="mobile-cal-header">Sa</div><div class="mobile-cal-header">Su</div>';

      const eventDates = new Set(calendarEvents.map((e) => e.date)); // Use state variable
      const firstDayCell = document.querySelector(
        ".calendar-grid tbody tr:first-child td:first-child"
      );
      let currentDate = new Date(firstDayCell.dataset.date + "T12:00:00");

      for (let i = 0; i < 42; i++) {
        // Loop up to 6 weeks for all possible layouts
        const dayDateStr = currentDate.toISOString().split("T")[0];
        const dayMonthStr = dayDateStr.substring(0, 7);

        let classes = "mobile-cal-day";
        if (dayMonthStr !== currentMonthStr) classes += " other-month";
        if (dayDateStr === todayDateStr) classes += " is-today";
        if (dayDateStr === selectedDateStr) classes += " is-selected";

        html += `<div class="${classes}" data-date="${dayDateStr}">
                    ${currentDate.getDate()}
                    ${
                      eventDates.has(dayDateStr)
                        ? '<div class="event-dot"></div>'
                        : ""
                    }
                </div>`;

        currentDate.setDate(currentDate.getDate() + 1);
        // Stop if we've rendered past the last cell in the grid
        if (
          document.querySelector(`.calendar-day[data-date="${dayDateStr}"]`) ===
          null
        )
          break;
      }
      navigator.innerHTML = html;
    };

    /**
     * Renders the scrollable agenda list for a specific day.
     * @param {string} dateStr - The date to render events for ('YYYY-MM-DD').
     * @param {Array} allEvents - The complete list of events for the month.
     */
    const renderAgendaForDate = (dateStr) => {
      const agendaList = document.getElementById("mobile-agenda-list");
      const eventsForDay = calendarEvents // Use state variable
        .filter((e) => e.date === dateStr)
        .sort((a, b) => a.eventTime.localeCompare(b.eventTime)); // Sort by time

      if (eventsForDay.length === 0) {
        agendaList.innerHTML = `
                <div class="agenda-empty-state">
                    <i class="bi bi-calendar-check"></i>
                    <p>No events scheduled.</p>
                </div>
            `;
        return;
      }

      let html = '<div class="card shadow-sm">';
      eventsForDay.forEach((event) => {
        // Add all necessary data attributes to the agenda item so the view modal can use it.
        html += `
            <div class="agenda-item" 
                 data-event-id="${event.eventId}"
                 data-event-title="${event.eventTitle}"
                 data-event-time="${event.eventTime}"
                 data-event-author="${event.eventAuthor}"
                 data-event-author-id="${event.eventAuthorId}">
                <div class="agenda-time">${event.eventTime}</div>
                <div class="agenda-details">
                    <div class="agenda-title">${event.eventTitle}</div>
                    <div class="agenda-author">Added by ${event.eventAuthor}</div>
                </div>
                <i class="bi bi-chevron-right text-muted"></i>
            </div>
            `;
      });
      html += "</div>";
      agendaList.innerHTML = html;
    };

    /**
     * Main function to re-render the entire mobile view.
     * Called on load and after any real-time update.
     */
    const refreshMobileCalendar = () => {
      const todayCell = document.querySelector(".calendar-day.today");
      const currentMonthStr = todayCell
        ? todayCell.dataset.date.substring(0, 7)
        : document.querySelector(".calendar-day").dataset.date.substring(0, 7);
      const todayDateStr = todayCell ? todayCell.dataset.date : null;
      const selectedDateStr =
        document.getElementById("mobile-month-navigator").dataset
          .selectedDate || todayDateStr;

      // No longer need to parse events here. We just render from state.
      renderMobileMonthNavigator(
        selectedDateStr,
        todayDateStr,
        currentMonthStr
      );
      renderAgendaForDate(selectedDateStr);
    };

    // --- B. INITIALIZATION & EVENT LISTENERS ---

    // 1. Initial Render on Page Load
    initializeEventsState();
    refreshMobileCalendar();

    // 2. Handle Tapping a Day in the Navigator
    mobileCalendarContainer.addEventListener("click", (e) => {
      const dayElement = e.target.closest(".mobile-cal-day");
      if (!dayElement || dayElement.classList.contains("other-month")) return;

      const newSelectedDate = dayElement.dataset.date;

      // Re-render navigator to update the 'is-selected' class
      const todayCell = document.querySelector(".calendar-day.today");
      const todayDateStr = todayCell ? todayCell.dataset.date : null;
      const currentMonthStr = todayDateStr
        ? todayDateStr.substring(0, 7)
        : document.querySelector(".calendar-day").dataset.date.substring(0, 7);

      // No need to parse events, just render.
      renderMobileMonthNavigator(
        newSelectedDate,
        todayDateStr,
        currentMonthStr
      );
      renderAgendaForDate(newSelectedDate);
    });

    // 3. Handle Tapping an Agenda Item to View Details
    document
      .getElementById("mobile-agenda-list")
      .addEventListener("click", (e) => {
        const item = e.target.closest(".agenda-item");
        if (!item) return;

        const viewModalEl = document.getElementById("viewEventModal");
        const viewModal = bootstrap.Modal.getInstance(viewModalEl);
        if (viewModal) {
          // Pass the item as the 'relatedTarget' so the modal's 'show.bs.modal'
          // event can read its data attributes, just like it does for event badges.
          viewModal.show(item);
        }
      });

    // 4. Handle FAB click to open "Add Event" modal for the selected day
    const mobileFab = document.getElementById("mobile-add-event-fab");
    if (mobileFab) {
      mobileFab.addEventListener("click", () => {
        const selectedDate = document.getElementById("mobile-month-navigator")
          .dataset.selectedDate;
        const dateInput = document.getElementById("event-date-input");
        const modalTitle = document.getElementById("addEventModalLabel");

        if (selectedDate && dateInput && modalTitle) {
          // Pre-fill the modal with the currently selected date in the mobile view
          dateInput.value = selectedDate;
          modalTitle.textContent = `Add Event for ${selectedDate}`;
        }
      });
    }

    // --- C. REAL-TIME SYNCHRONIZATION ---
    // We now update our local state directly from socket messages, then re-render.

    socket.on("event_added", (data) => {
      // Create a new event object in the same format as our state objects.
      const newEvent = {
        eventId: data.event.id.toString(),
        eventTitle: data.event.title,
        eventTime: data.event.formatted_time,
        eventAuthor: data.event.author.username,
        eventAuthorId: data.event.author.id.toString(),
        date: data.event.date,
      };
      // Add the new event to our state.
      calendarEvents.push(newEvent);
      // Re-render the mobile UI.
      refreshMobileCalendar();
    });

    socket.on("event_deleted", (data) => {
      // Filter our state to remove the deleted event.
      calendarEvents = calendarEvents.filter(
        (event) => event.eventId != data.event_id
      );
      // Re-render the mobile UI.
      refreshMobileCalendar();
    });

    socket.on("event_updated", (data) => {
      // Find the event in our state.
      const eventToUpdate = calendarEvents.find(
        (event) => event.eventId == data.event.id
      );
      if (eventToUpdate) {
        // Update its properties.
        eventToUpdate.eventTitle = data.event.title;
        eventToUpdate.eventTime = data.event.formatted_time;
      }
      // Re-render the mobile UI.
      refreshMobileCalendar();
    });
  }
  // =======================================================
  // END: NEW MOBILE CALENDAR & AGENDA VIEW LOGIC
  // =======================================================
});
