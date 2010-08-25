package com.example;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Calendar;
import java.util.Collections;
import java.util.List;

public class Calculator implements Serializable
{

  private int value = 1;
  
  public int add(int addend)
  {
    int sum = value + addend;
    value = sum;
    return value;
  }

  public void print(String prefix)
  {
    System.out.println(prefix + value);
  }

}
