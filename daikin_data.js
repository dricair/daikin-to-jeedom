#!/usr/bin/env node
/**
 * File copied and modified from Daikin-Controller-Cloud token saver example
 *
 * Get raw daikin data and save it to JSON file (One per device)
 */

 const DaikinCloud = require('daikin-controller-cloud/index');
 const fs = require('fs');
 const path = require('path');


 async function main() {
     /**
      * Options to initialize the DaikinCloud instance with
      */
     const options = {
         logger: console.log,          // optional, logger function used to log details depending on loglevel
         logLevel: 'info',             // optional, Loglevel of Library, default 'warn' (logs nothing by default)
         proxyOwnIp: '127.0.0.1',      // required, if proxy needed: provide own IP or hostname to later access the proxy
         proxyPort: 8888,              // required: use this port for the proxy and point your client device to this port
         proxyWebPort: 8889,           // required: use this port for the proxy web interface to get the certificate and start Link for login
         proxyListenBind: '0.0.0.0',   // optional: set this to bind the proxy to a special IP, default is '0.0.0.0'
         proxyDataDir: process.cwd(),  // Directory to store certificates and other proxy relevant data to
         communicationTimeout: 10000,  // Amount of ms to wait for request and responses before timeout
         communicationRetries: 3       // Amount of retries when connection timed out
     };

     let tokenSet;

    // Set outputfile for tokenset.json
    const tokenFile = path.join(process.cwd(), 'tokenset.json');
    options.logger('Writing tokenset to: ' + tokenFile);

    // Initialize Daikin Cloud Instance
    const daikinCloud = new DaikinCloud(tokenSet, options);

    // Event that will be triggered on new or updated tokens, save into file
    daikinCloud.on('token_update', tokenSet => {
        console.log(`UPDATED tokens, use for future and wrote to tokenset.json`);
        fs.writeFileSync(tokenFile, JSON.stringify(tokenSet));
    });

    let args = process.argv.slice(2);
    if (args.length === 2 && args[0].includes('@')) {
        console.log(`Using provided Login credentials (${args[0]}/${args[1]}) for a direct Login`)
        const resultTokenSet = await daikinCloud.login(args[0], args[1]);
        console.log('Retrieved tokens. Saved to ' + tokenFile);
    } else {
        if (args.length && !args[0].includes('@')) {
            console.log('Ignore provided parameters because first parameter do not seem to be an email address');
            console.log();
        }
        await daikinCloud.initProxyServer();

        console.log(`Please visit http://${options.proxyOwnIp}:${options.proxyWebPort} and Login to Daikin Cloud please.`);
        // wait for user Login and getting the tokens
        const resultTokenSet = await daikinCloud.waitForTokenFromProxy();
        console.log('Retrieved tokens. Saved to ' + tokenFile);
        //console.log(`Retrieved tokens, use for future: ${JSON.stringify(resultTokenSet)}`);

        // stop Proxy server (and wait 1s before we do that to make sure
        // the success page can be displayed correctly because waitForTokenFromProxy
        // will resolve before the last request is sent to the browser!
        await new Promise(resolve => setTimeout(resolve, 1000));
        await daikinCloud.stopProxyServer();
    }

    const daikinDeviceDetails = await daikinCloud.getCloudDeviceDetails();
    // console.log(`Cloud Device Details: ${JSON.stringify(daikinDeviceDetails)}`);

    const devices = await daikinCloud.getCloudDevices();

    if (devices && devices.length) {
        for (let dev of devices) {
            // console.log('Device ' + dev.getId() + ' Data:');
            // console.log('    last updated: ' + dev.getLastUpdated());
            // console.log('    modelInfo: ' + dev.getData('gateway', 'modelInfo').value);
            // console.log('    temp auto set room: ' + dev.getData('climateControl', 'temperatureControl', '/operationModes/auto/setpoints/roomTemperature').value);
            // console.log('    Full mapped description: ' + JSON.stringify(dev.getData(), null, 2));

            const outputFile = path.join(process.cwd(), dev.getId() + '.json');
            console.log("Output file: " + outputFile);
            fs.writeFileSync(outputFile, JSON.stringify(dev.getData(), null, 2));

            // only partially tested, needs to be checked!!
            // await dev.setData('gateway', 'ledEnabled', true);
            // await dev.setData('climateControl', 'onOffMode', 'on');
            // await dev.setData('climateControl', 'temperatureControl', '/operationModes/auto/setpoints/roomTemperature', 20);
            // await dev.updateData();
        }
    } else {
        console.log('No devices returned');
    }

    process.exit();
 }

 (async () => {
     await main();
 })();

