/** Plain steps shown under each hotel feature. Keep them true to the screen they sit on. */
export type HotelGuideText = {
  what: string;
  steps: string[];
  tip?: string;
};

export const HOTEL_GUIDES: Record<string, HotelGuideText> = {
  dashboard: {
    what: 'Your day at a glance. Press any tile or line to go straight to the work. A normal day runs like this:',
    steps: [
      'Morning: open Front desk and see who is arriving and leaving.',
      'When a guest arrives, press Check in. Their bill opens by itself.',
      'During the stay, add meals, laundry and extras to the bill.',
      'When they leave, take the payment and press Check out. Housekeeping gets the room to clean.',
      'Night: count the drawer and run the night audit under Cash and night audit.',
    ],
  },
  'front-desk': {
    what: 'Your working screen for today: who comes in, who goes out, and every room.',
    steps: [
      'Press a tile to see arrivals, departures or guests in the house.',
      'Press Check in when the guest arrives. Press Check out when they leave.',
      'Press Bill to add charges or take a payment.',
      'Use the room board below: a guest opens their bill, an empty room starts a booking.',
    ],
    tip: 'A room that needs cleaning cannot be booked for today. Mark it clean under Housekeeping first. You will be warned if a guest is checked in to it.',
  },
  reservations: {
    what: 'Every stay, past and future. Use the buttons below to change what you see.',
    steps: [
      'Stays lists every booking. Search by guest, phone, room or number.',
      'Calendar shows each room by date. Press an empty night to book it.',
      'Book a stay takes a new booking in three steps.',
      'Use the menu on a row to extend, change room, edit or cancel.',
    ],
  },
  'book-stay': {
    what: 'Three steps: dates, room, guest.',
    steps: [
      'Pick the dates and how many people. Free rooms appear by themselves.',
      'Press a room to choose it. The price shows at the bottom.',
      'Type the guest name. Pick them from the list, or leave the name as it is to add a new guest.',
      'Press Book stay. Tick Walk-in if the guest is standing at the desk.',
    ],
    tip: 'Discount, deposit and rate plan are under More options.',
  },
  'group-stay': {
    what: 'One booking for several rooms, such as a family or a company.',
    steps: [
      'Pick the dates. Only rooms free on those dates are shown.',
      'Tick two or more rooms.',
      'Choose the person who is booking and give the group a name.',
      'Press Book group. Each room gets its own stay and its own bill.',
    ],
  },
  'online-booking': {
    what: 'A page where guests ask for a room from your website. It does not take payment.',
    steps: [
      'Type your website address and press Save booking link.',
      'Copy the link and put it on your website.',
      'A guest request appears under Stays as Tentative and holds the room.',
      'Press Confirm booking to accept it.',
    ],
  },
  rooms: {
    what: 'Your rooms and what each one costs.',
    steps: [
      'Press Add room for each room you sell.',
      'Set the nightly rate. Add a weekend rate if Saturday and Sunday nights cost more.',
      'Press Edit on a row to change the price or details.',
      'Stop selling a room you no longer use. Its old stays stay on record.',
    ],
    tip: 'To close a room for repairs, report the fault under Maintenance.',
  },
  'rate-plans': {
    what: 'A special nightly price you can pick when booking, such as a corporate or long-stay rate.',
    steps: [
      'Press Add rate plan and give it a code, a name and a nightly price.',
      'Limit it to a room type, dates, or a minimum number of nights if you need to.',
      'When booking, choose it under More options.',
      'Turn a plan off when the offer ends. Stays already booked keep their price.',
    ],
  },
  housekeeping: {
    what: 'Rooms to clean. A task is added by itself when a guest checks out.',
    steps: [
      'Open To do and see which rooms need work.',
      'Clean the room, then press Mark clean. The room is ready to sell again.',
      'Press Add task for anything extra, such as a linen change.',
    ],
    tip: 'A room with an open maintenance fault stays closed until the fault is fixed.',
  },
  'lost-found': {
    what: 'Things guests left behind, and damage found in a room.',
    steps: [
      'Press Record an item and describe it.',
      'Add the room if you know it.',
      'Press Close when the item goes back to the guest or the matter is settled.',
    ],
  },
  maintenance: {
    what: 'Faults in rooms, and whether the room can still be sold.',
    steps: [
      'Press Report a fault and pick the room.',
      'Leave Stop selling this room ticked if guests cannot use it.',
      'Leave the dates empty to close the room until the fault is fixed, or set dates to close only those nights.',
      'Press Mark fixed when it is done. The room opens again.',
    ],
  },
  guests: {
    what: 'Everyone who has stayed or booked.',
    steps: [
      'Search by name, phone or email.',
      'Press Details to see their stays and what they owe.',
      'Press Edit to change their phone, ID or notes.',
      'Same guest twice? Open Details on the one to keep and merge the other into it.',
    ],
  },
  services: {
    what: 'Your price list of extras: laundry, spa, airport pick-up, meals and drinks.',
    steps: [
      'Press Add service and set the price.',
      'Choose Restaurant or Bar for meals and drinks. They then appear on those desks.',
      'To charge a guest, open their bill under Guest bills.',
      'Press Edit to change a price, or turn a service off.',
    ],
    tip: 'Tax % here is added when the service goes on a bill. Room tax is set under Hotel settings.',
  },
  restaurant: {
    what: 'Put meals and drinks on a guest’s room bill. This is not a till and it does not charge a card.',
    steps: [
      'Pick the guest bill.',
      'Press the item from your menu and set how many.',
      'Press Post to bill. The guest pays at check-out.',
    ],
    tip: 'Your menu comes from Hotel services. Something not on the menu? Use One-off item.',
  },
  billing: {
    what: 'What each guest has been charged and has paid. A bill opens when the guest checks in.',
    steps: [
      'Find the guest and press View bill.',
      'Add charges during the stay.',
      'Take the payment. The amount still owed is filled in for you.',
      'Press Check out when the bill is settled.',
    ],
    tip: 'Payments reach Accounting by themselves. A guest who left owing is collected under Guest invoices.',
  },
  cashier: {
    what: 'Your front-desk cash, and closing the day. Do these in order.',
    steps: [
      'Start of shift: count the drawer and press Open front-desk float.',
      'Cash payments on guest bills are added up for you.',
      'End of shift: count the drawer, type the amount and press Close front-desk float. You will see if it is over or short.',
      'End of day: press Run night audit to save the day.',
    ],
    tip: 'Hotel costs go under Expenses, not here.',
  },
  reports: {
    what: 'How the hotel is doing over the dates you choose, compared with the days just before.',
    steps: [
      'Pick dates, or press Today, Last 7 days, This month or Last month.',
      'Overview shows how full you were and what you earned. The arrows compare with the same number of days before. Move over a chart to read a day.',
      'Rooms shows what each room earns. Income shows booking sources, how guests paid and extras. Money owed shows who to collect from.',
      'Press Download CSV for a spreadsheet, or Print for paper.',
    ],
    tip: 'Occupancy is how full you were. ADR is the average price of a room sold. RevPAR is income per room you had to sell.',
  },
  events: {
    what: 'Weddings, meetings and banquets in your halls.',
    steps: [
      'Press Book an event and give the name, the hall and the dates.',
      'Hold a guest room only if the event needs one. That room cannot be booked for those dates.',
      'Add a deposit if one was paid.',
    ],
    tip: 'A deposit reaches the books when the organizer has an open bill.',
  },
  invoices: {
    what: 'Each stay becomes an invoice at check-out. This is where you collect what is still owed.',
    steps: [
      'Owed shows every unpaid invoice. All shows the paid ones too.',
      'Search by guest, company, room or invoice number.',
      'Open an invoice and take the payment. It reaches Accounting by itself.',
    ],
    tip: 'A guest still staying pays on their bill under Guest bills, not here.',
  },
  shop: {
    what: 'Sell shop items at the desk, for cash or to a guest’s room.',
    steps: [
      'Open a front-desk shift if none is open.',
      'Tap items to fill the basket.',
      'Press Take payment. Choose how they pay, or put it on their room bill.',
    ],
    tip: 'Items come from Supplies. An item needs a selling price to show here.',
  },
  supplies: {
    what: 'Linen, toiletries, food, drink and cleaning items.',
    steps: [
      'Add each item once under Supplies.',
      'Order from your supplier with a Purchase order.',
      'When the goods arrive, use Receive supplies. Stock goes up by itself.',
      'Low supplies shows what to buy next.',
    ],
  },
  settings: {
    what: 'Set these once. They apply to every stay.',
    steps: [
      'Check the hotel name and your check-in and check-out times.',
      'Set your tax, and say if your room rates already include it.',
      'Set any fees you charge. Leave a fee at 0 if you do not charge it.',
      'Press Save settings.',
    ],
  },
};
