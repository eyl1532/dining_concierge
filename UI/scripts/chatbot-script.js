var chatHistory = [];
var apigClient = null;

var url_string = window.location.href;
var cognito_token = url_string.substring(url_string.indexOf("=") + 1,url_string.indexOf("&"));

AWS.config.region = 'us-east-1';
AWS.config.credentials = new AWS.CognitoIdentityCredentials({
  IdentityPoolId: 'Your Identity Pool ID',
	Logins: {
	   'cognito-idp.us-east-1.amazonaws.com/us-east-1_8MsV07uIJ': cognito_token
	}
});

function callChatbotLambda() {
  var inputText = document.getElementById('user-input-text').value.trim().toLowerCase();
  document.getElementById('user-input-text').value = "";
  if(inputText == "") {
    alert("Please enter some text");
    return false;
  }else {
    chatHistory.push("User: " + inputText);
    document.getElementById('chat-output').innerHTML = "";
    chatHistory.forEach((element) => {
      document.getElementById('chat-output').innerHTML += "<p>" + element + "</p>";
    });
    setTimeout(chatbotResponse, 500, inputText);
    return false;
  }
}

function chatbotResponse(inputText) {
  return AWS.config.credentials.getPromise()
  .then(()=>{
    console.log('Successfully logged!');
    apigClient = apigClientFactory.newClient({
      accessKey: AWS.config.credentials.accessKeyId,
      secretKey: AWS.config.credentials.secretAccessKey,
      sessionToken: AWS.config.credentials.sessionToken
    });
    var params = {};
    var body = {
      "message":inputText,
      "identityID":AWS.config.credentials._identityId
    };
    var additionalParams = {
      headers: {
        'x-api-key': 'Your API KEY'
      },
      queryParams: {}
    };
    return apigClient.chatbotPost(params,body,additionalParams);
  })
  .then((result) =>{
      chatHistory.push("Bot: " + result.data.body);
      document.getElementById('chat-output').innerHTML = "";
      chatHistory.forEach((element) => {
        document.getElementById('chat-output').innerHTML += "<p>" + element + "</p>";
      });
  })
  .catch((err) =>{
    console.log(err);
  });
}
