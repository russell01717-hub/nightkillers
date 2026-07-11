let button = document.querySelector(".btn")


button.style.backgroundColor = "red";
button.style.border = "none"
button.style.whith = "135px";
button.style.hieght = "45px";

let number = 0;

button.addEventListener("mousemove", function() {
    console.log(number += 1)
})