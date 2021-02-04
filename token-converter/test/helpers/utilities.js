const checkGetOrders = (orders, _ordersIds, _ordersAmounts) => {
  let i = 0;
  let checkOrdersOk = true;
  let ordersIds = orders[0].slice();
  let ordersAmounts = orders[1].slice();

  ordersIds = ordersIds.filter((item) => item);
  ordersAmounts = ordersAmounts.filter((item) => item);

  while (ordersIds[i] != 0) {
    if (ordersIds[i].toNumber() != _ordersIds[i]) {
      checkOrdersOk = false;
      break;
    }

    if (ordersAmounts[i].toNumber() != _ordersAmounts[i]) {
      checkOrdersOk = false;
      break;
    }
    i++;
  }

  return { checkOrdersOk, qty: i };
};

const makeSellOrder = async (converterContract, amount, tokenAddress, sellerAddress, txOption) => {
  const tx = await converterContract.onTokensMinted(
      amount,
      tokenAddress,
      web3.eth.abi.encodeParameter("address", sellerAddress),
      txOption
  );

  const makeSellOrderLog = tx.logs[1];
  return makeSellOrderLog.args._orderId.toNumber();
}

module.exports = {
  checkGetOrders,
  makeSellOrder
};
